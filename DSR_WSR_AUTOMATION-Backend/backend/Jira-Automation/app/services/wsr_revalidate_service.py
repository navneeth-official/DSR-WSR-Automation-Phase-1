"""Re-check a WSR deck: pull the latest SharePoint copy (when configured) and re-validate.

Slide Review only ever shows the *last stored* validation snapshot. This service backs the
separate "Re-check deck" action:

1. Resolve the local deck + template.
2. When SharePoint is the active provider (and ``from_sharepoint``), read the remote item's
   eTag. If it equals the fingerprint from the last check (and a report exists) and the
   caller did not ``force`` it, return ``unchanged`` without downloading or validating.
3. Otherwise download the remote file over the local deck, then run ``run_wsr_validation``
   (report JSON + annotated PNGs).
4. Remember the remote eTag in ``WSR_*_validation_fingerprint.json``.

If SharePoint cannot be reached but the local deck exists, the local copy is validated.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timezone
from typing import Any

from app.paths import (
    wsr_validation_error_path,
    wsr_validation_fingerprint_path,
    wsr_validation_report_path,
)
from app.services.cloud_upload_service import resolve_cloud_provider
from app.services.sharepoint_upload_service import (
    download_ppt_from_sharepoint,
    get_sharepoint_item_metadata,
    load_sharepoint_item_meta,
    save_sharepoint_item_meta,
)
from app.services.wsr_validation_service import (
    get_validation_status,
    run_wsr_validation,
)
from app.services.wsr_variant_service import list_week_variants, resolve_variant_paths

logger = logging.getLogger(__name__)

UNCHANGED_MESSAGE = (
    "SharePoint copy matches the last check — skipped download and re-validation."
)


class RevalidateBusyError(RuntimeError):
    """A re-check for the same deck is already running."""


_running_guard = threading.Lock()
_running: set[tuple[date, date, int]] = set()


# ── Fingerprint ───────────────────────────────────────────────────────────────

def load_validation_fingerprint(
    start_date: date, end_date: date, *, variant: int = 1
) -> dict[str, Any] | None:
    path = wsr_validation_fingerprint_path(start_date, end_date, variant=variant)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _save_validation_fingerprint(
    start_date: date,
    end_date: date,
    *,
    variant: int,
    template_id: str | None,
    filename: str,
    item: dict[str, Any],
) -> None:
    payload = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "source": "sharepoint",
        "filename": filename,
        "variant": variant,
        "template_id": template_id,
        "eTag": item.get("eTag"),
        "id": item.get("id"),
        "lastModifiedDateTime": item.get("lastModifiedDateTime"),
        "driveId": item.get("driveId"),
        "webUrl": item.get("webUrl"),
    }
    path = wsr_validation_fingerprint_path(start_date, end_date, variant=variant)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def record_validation_fingerprint_from_sharepoint(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
    template_id: str | None = None,
) -> bool:
    """Best effort: remember the SharePoint version a fresh validation corresponds to.

    Called after post-generation validation so the first Re-check can be skipped when
    nobody edited the SharePoint copy. Never raises.
    """
    try:
        if resolve_cloud_provider() != "sharepoint":
            return False
        filename = resolve_variant_paths(start_date, end_date, variant).ppt_path.name
        item = load_sharepoint_item_meta(start_date, end_date, variant=variant)
        if not item or not item.get("eTag"):
            # Decks uploaded before eTags were stored: ask Graph once.
            item = get_sharepoint_item_metadata(filename)
        if not item.get("eTag"):
            return False
        _save_validation_fingerprint(
            start_date,
            end_date,
            variant=variant,
            template_id=template_id or _template_id_for_variant(start_date, end_date, variant),
            filename=filename,
            item=item,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - best effort only
        logger.info("Could not record validation fingerprint: %s", exc)
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _template_id_for_variant(start_date: date, end_date: date, variant: int) -> str | None:
    for item in list_week_variants(start_date, end_date):
        if int(item.get("variant") or 1) == variant:
            return item.get("template_id")
    return None


def _report_summary(start_date: date, end_date: date, variant: int) -> dict[str, Any]:
    path = wsr_validation_report_path(start_date, end_date, variant=variant)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    summary = report.get("summary") or {}
    fail = int(summary.get("fail") or 0)
    warn = int(summary.get("warn") or 0)
    return {
        "deck_pass": bool(report.get("deck_pass")),
        "findings_count": int(summary.get("total_findings", fail + warn) or 0),
        "fail_count": fail,
        "warn_count": warn,
    }


def _validation_failure_message(start_date: date, end_date: date, variant: int) -> str:
    error_path = wsr_validation_error_path(start_date, end_date, variant=variant)
    try:
        data = json.loads(error_path.read_text(encoding="utf-8"))
        if data.get("message"):
            return str(data["message"])
    except (OSError, json.JSONDecodeError):
        pass
    status = get_validation_status(start_date, end_date, variant=variant)
    return str(status.get("message") or "Validation failed.")


def _result(
    *,
    status: str,
    message: str,
    variant: int,
    template_id: str | None,
    from_sharepoint: bool,
    pulled: bool,
    force: bool,
    etag: str | None,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "from_sharepoint": from_sharepoint,
        "pulled": pulled,
        "force": force,
        "variant": variant,
        "template_id": template_id,
        "eTag": etag,
        "deck_pass": summary.get("deck_pass"),
        "findings_count": summary.get("findings_count"),
        "fail_count": summary.get("fail_count"),
        "warn_count": summary.get("warn_count"),
    }


# ── Public entry point ────────────────────────────────────────────────────────

def revalidate_wsr_deck(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
    template_id: str | None = None,
    from_sharepoint: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Re-check one deck. Raises FileNotFoundError / RuntimeError / RevalidateBusyError."""
    key = (start_date, end_date, variant)
    with _running_guard:
        if key in _running:
            raise RevalidateBusyError("A re-check for this deck is already running.")
        _running.add(key)
    try:
        return _revalidate(
            start_date,
            end_date,
            variant=variant,
            template_id=template_id,
            from_sharepoint=from_sharepoint,
            force=force,
        )
    finally:
        with _running_guard:
            _running.discard(key)


def _revalidate(
    start_date: date,
    end_date: date,
    *,
    variant: int,
    template_id: str | None,
    from_sharepoint: bool,
    force: bool,
) -> dict[str, Any]:
    if get_validation_status(start_date, end_date, variant=variant)["status"] == "pending":
        raise RevalidateBusyError("Validation is already running for this deck.")

    ppt_path = resolve_variant_paths(start_date, end_date, variant).ppt_path
    template_id = template_id or _template_id_for_variant(start_date, end_date, variant)

    use_sharepoint = from_sharepoint and resolve_cloud_provider() == "sharepoint"

    notes: list[str] = []
    remote: dict[str, Any] | None = None
    pulled = False

    if use_sharepoint:
        try:
            remote = get_sharepoint_item_metadata(ppt_path.name)
        except Exception as exc:  # noqa: BLE001 - fall back to the local deck below
            if not ppt_path.is_file():
                if isinstance(exc, FileNotFoundError):
                    raise FileNotFoundError(
                        f"{ppt_path.name} is not on this server or in SharePoint."
                    ) from exc
                raise RuntimeError(f"Could not read the deck from SharePoint: {exc}") from exc
            logger.warning("SharePoint metadata lookup failed for %s: %s", ppt_path.name, exc)
            notes.append("SharePoint was unavailable, so the local copy was checked.")

    if remote is None and not ppt_path.is_file():
        raise FileNotFoundError(f"WSR deck not found: {ppt_path.name}")

    if not template_id:
        raise FileNotFoundError(
            "Could not determine which template this deck was generated with. "
            "Pass template_id explicitly."
        )

    if remote is not None:
        etag = remote.get("eTag")
        fingerprint = load_validation_fingerprint(start_date, end_date, variant=variant)
        report_ready = (
            wsr_validation_report_path(start_date, end_date, variant=variant).is_file()
            and get_validation_status(start_date, end_date, variant=variant)["status"] == "ready"
        )
        if (
            not force
            and etag
            and fingerprint
            and fingerprint.get("eTag") == etag
            and report_ready
        ):
            return _result(
                status="unchanged",
                message=UNCHANGED_MESSAGE,
                variant=variant,
                template_id=template_id,
                from_sharepoint=True,
                pulled=False,
                force=force,
                etag=etag,
                summary=_report_summary(start_date, end_date, variant),
            )

        try:
            download_ppt_from_sharepoint(ppt_path.name, ppt_path)
            pulled = True
        except Exception as exc:  # noqa: BLE001
            if not ppt_path.is_file():
                raise RuntimeError(f"Could not download the deck from SharePoint: {exc}") from exc
            logger.warning("SharePoint download failed for %s: %s", ppt_path.name, exc)
            notes.append("The SharePoint copy could not be downloaded, so the local copy was checked.")
            remote = None

    summary = run_wsr_validation(
        start_date, end_date, variant=variant, template_id=template_id
    )
    if summary is None or not wsr_validation_report_path(
        start_date, end_date, variant=variant
    ).is_file():
        raise RuntimeError(_validation_failure_message(start_date, end_date, variant))

    etag = None
    if pulled and remote is not None:
        etag = remote.get("eTag")
        try:
            _save_validation_fingerprint(
                start_date,
                end_date,
                variant=variant,
                template_id=template_id,
                filename=ppt_path.name,
                item=remote,
            )
            existing = load_sharepoint_item_meta(start_date, end_date, variant=variant) or {}
            save_sharepoint_item_meta(
                start_date, end_date, {**existing, **remote}, variant=variant
            )
        except Exception as exc:  # noqa: BLE001 - bookkeeping must not fail the check
            logger.warning("Could not save validation fingerprint: %s", exc)

    if pulled:
        message = "Pulled the latest SharePoint copy and re-validated the deck."
    else:
        message = "Re-validated the local deck."
    if notes:
        message = f"{message} {' '.join(notes)}"

    return _result(
        status="validated",
        message=message,
        variant=variant,
        template_id=template_id,
        from_sharepoint=pulled,
        pulled=pulled,
        force=force,
        etag=etag,
        summary=_report_summary(start_date, end_date, variant),
    )
