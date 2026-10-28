"""Run deck validation for generated WSR decks and track its status on disk.

Validation runs *after* generation has been reported as completed, so the UI polls
``get_validation_status`` until the report exists. Failures never affect the deck
or the generation job: they are recorded in ``WSR_*_validation_error.json``.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pptx.exc import PackageNotFoundError

from app.paths import (
    OUTPUT_DIR,
    ensure_output_dir,
    wsr_validation_dir,
    wsr_validation_error_path,
    wsr_validation_report_md_path,
    wsr_validation_report_path,
    wsr_validation_status_path,
)
from app.services import wsr_deck_store as deck_store
from app.services.wsr_template_upload_service import resolve_template_path
from app.services.wsr_variant_service import list_week_variants, resolve_variant_paths

logger = logging.getLogger(__name__)

# Locked / half-written .pptx files (e.g. the cloud sync or a preview export still
# holding the file) are retried before we give up.
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 15
# A "running" marker older than this means the server restarted mid-run.
STALE_RUNNING_SECONDS = 10 * 60

ANNOTATION_GLOB = "slide_*_*.png"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_status(
    start_date: date,
    end_date: date,
    variant: int,
    state: str,
    message: str | None = None,
    **extra: Any,
) -> None:
    ensure_output_dir()
    payload = {"state": state, "message": message, "updated_at": _now(), **extra}
    wsr_validation_status_path(start_date, end_date, variant=variant).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def clear_validation_artifacts(start_date: date, end_date: date, *, variant: int = 1) -> None:
    """Remove previous report / annotations so stale results are never served."""
    for path in (
        wsr_validation_report_path(start_date, end_date, variant=variant),
        wsr_validation_report_md_path(start_date, end_date, variant=variant),
        wsr_validation_error_path(start_date, end_date, variant=variant),
    ):
        path.unlink(missing_ok=True)
    shutil.rmtree(wsr_validation_dir(start_date, end_date, variant=variant), ignore_errors=True)


def begin_validation(start_date: date, end_date: date, *, variant: int = 1) -> None:
    """Mark validation as pending (clears old artefacts)."""
    clear_validation_artifacts(start_date, end_date, variant=variant)
    _write_status(start_date, end_date, variant, "running", "Validation in progress")


def has_annotation_images(start_date: date, end_date: date, *, variant: int = 1) -> bool:
    directory = wsr_validation_dir(start_date, end_date, variant=variant)
    return directory.is_dir() and any(directory.glob(ANNOTATION_GLOB))


def get_validation_status(start_date: date, end_date: date, *, variant: int = 1) -> dict[str, Any]:
    """
    Return ``{"status": "ready" | "pending" | "error" | "not_started", "has_annotations": bool, "message"?}``.
    """
    report = wsr_validation_report_path(start_date, end_date, variant=variant)
    state_file = _read_json(wsr_validation_status_path(start_date, end_date, variant=variant))
    state = (state_file or {}).get("state")

    if state == "running":
        updated = (state_file or {}).get("updated_at")
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(updated))).total_seconds()
        except (TypeError, ValueError):
            age = 0
        if age <= STALE_RUNNING_SECONDS:
            return {"status": "pending", "has_annotations": False, "message": "Validation in progress"}
        return {
            "status": "error",
            "has_annotations": False,
            "message": "Validation was interrupted. Run it again.",
        }

    if report.is_file():
        return {
            "status": "ready",
            "has_annotations": has_annotation_images(start_date, end_date, variant=variant),
        }

    error = _read_json(wsr_validation_error_path(start_date, end_date, variant=variant))
    if error or state == "error":
        message = (error or {}).get("message") or (state_file or {}).get("message")
        return {
            "status": "error",
            "has_annotations": False,
            "message": message or "Validation failed.",
        }

    return {"status": "not_started", "has_annotations": False}


def _template_id_for_variant(start_date: date, end_date: date, variant: int) -> str | None:
    for item in list_week_variants(start_date, end_date):
        if int(item.get("variant") or 1) == variant:
            return item.get("template_id")
    return None


def _write_error(start_date: date, end_date: date, variant: int, exc: BaseException) -> None:
    message = f"{type(exc).__name__}: {exc}"
    try:
        wsr_validation_error_path(start_date, end_date, variant=variant).write_text(
            json.dumps(
                {"error": type(exc).__name__, "message": message, "failed_at": _now()},
                indent=2,
            ),
            encoding="utf-8",
        )
        _write_status(start_date, end_date, variant, "error", message)
    except OSError:
        logger.exception("Could not record validation error")


def run_wsr_validation(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
    template_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Validate a generated WSR deck and write the report + annotated PNGs per deck.

    Never raises: on failure the error is written to ``_validation_error.json`` and
    ``None`` is returned, so deck generation is unaffected.
    """
    from app.validation.engine import validate_deck

    try:
        # Uses the cached deck, downloading it from SharePoint when the cache was cleaned.
        ppt_path = deck_store.ensure_local_deck(start_date, end_date, variant)

        begin_validation(start_date, end_date, variant=variant)

        template_id = template_id or _template_id_for_variant(start_date, end_date, variant)
        template_path = resolve_template_path(template_id)

        result = None
        last_error: BaseException | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = validate_deck(
                    ppt_path,
                    template_path=template_path,
                    output_dir=OUTPUT_DIR,
                    annotate=True,
                    use_rendered_bounds=False,
                    report_json_path=wsr_validation_report_path(start_date, end_date, variant=variant),
                    report_md_path=wsr_validation_report_md_path(start_date, end_date, variant=variant),
                    annotation_dir=wsr_validation_dir(start_date, end_date, variant=variant),
                )
                break
            except (PackageNotFoundError, PermissionError) as exc:
                last_error = exc
                logger.warning(
                    "Validation attempt %d/%d failed (file locked?): %s", attempt, MAX_ATTEMPTS, exc
                )
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_DELAY_SECONDS)
        if result is None:
            assert last_error is not None
            raise last_error

        # Raw renderer PNGs are only intermediates for the annotated images.
        shutil.rmtree(
            wsr_validation_dir(start_date, end_date, variant=variant) / "_slides",
            ignore_errors=True,
        )

        summary = {
            "deck_pass": result.deck_pass,
            "finding_count": len(result.findings),
            "fail": sum(1 for f in result.findings if f.get("severity") == "fail"),
            "warn": sum(1 for f in result.findings if f.get("severity") == "warn"),
        }
        _write_status(start_date, end_date, variant, "ready", None, **summary)

        try:
            from app.services.validation_upload_service import try_upload_validation_artifacts

            try_upload_validation_artifacts(start_date, end_date, variant=variant)
        except Exception as exc:  # noqa: BLE001 - upload is best effort
            logger.warning("Validation artefact upload failed: %s", exc)

        return summary
    except Exception as exc:  # noqa: BLE001 - validation must never break generation
        logger.exception("WSR validation failed for %s..%s v%s", start_date, end_date, variant)
        _write_error(start_date, end_date, variant, exc)
        return None
