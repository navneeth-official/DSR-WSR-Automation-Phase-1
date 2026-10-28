"""
One-time migration: upload everything in the old ``output/`` folder to SharePoint.

Since WSR templates and generated decks are stored only in SharePoint, run this once
(from backend/Jira-Automation with the venv active, on a machine that has the old
``output/`` files and the SharePoint settings in .env):

    python scripts/migrate_output_to_sharepoint.py --dry-run     # preview
    python scripts/migrate_output_to_sharepoint.py               # upload

Mapping (folders come from .env / app/config.py):

    output/wsr_templates/<id>.pptx|json      -> SHAREPOINT_TEMPLATE_FOLDER   (Shared Documents/WSR Template)
                                                saved under the ORIGINAL uploaded file name
                                                (e.g. "My Template.pptx"); manifests are updated
                                                to the new template ids
    output/WSR_UPLOADED_TEMPLATE.pptx        -> same folder (legacy single upload)
    output/WSR_<start>_<end>[_vN].pptx       -> SHAREPOINT_UPLOAD_FOLDER     (Shared Documents/WSR)
    output/WSR_*.json, *_preview.txt,
           *_manifest.json                   -> data folder                  (Shared Documents/WSR/_data)
    output/WSR_*_validation_report.json,
    output/WSR_*_validation/slide_*_*.png    -> <data folder>/<stem>_validation/

Files that already exist in SharePoint with the same size are skipped, so the script is
safe to re-run. Nothing is deleted locally; remove ``output/`` yourself once you have
checked SharePoint.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

_DATES = r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})"
DECK_RE = re.compile(rf"^WSR_{_DATES}(?:_v(\d+))?\.pptx$")
CONTENT_RE = re.compile(rf"^WSR_{_DATES}(?:_v\d+)?\.json$")
PREVIEW_RE = re.compile(rf"^WSR_{_DATES}(?:_v\d+)?_preview\.txt$")
MANIFEST_RE = re.compile(rf"^WSR_{_DATES}_manifest\.json$")
REPORT_RE = re.compile(rf"^(WSR_{_DATES}(?:_v\d+)?)_validation_report\.json$")
VALIDATION_DIR_RE = re.compile(rf"^(WSR_{_DATES}(?:_v\d+)?)_validation$")
ANNOTATION_RE = re.compile(r"^slide_\d+_[a-z0-9._-]+\.png$")
TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
LEGACY_TEMPLATE = "WSR_UPLOADED_TEMPLATE.pptx"
LEGACY_TEMPLATE_META = "WSR_UPLOADED_TEMPLATE.json"


@dataclass
class Upload:
    local: Path
    folder: str
    remote_name: str
    kind: str


def _slide_count(pptx: Path) -> int | None:
    try:
        from pptx import Presentation

        return len(Presentation(str(pptx)).slides)
    except Exception:  # noqa: BLE001
        return None


def _build_manifest_file(
    source: Path, start: str, end: str, work_dir: Path, id_map: dict[str, str]
) -> Path | None:
    """Manifest for one week (existing one enriched with slide counts, or a new one)."""
    manifest_path = source / f"WSR_{start}_{end}_manifest.json"
    manifest: dict = {"report_start_date": start, "report_end_date": end, "variants": []}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
                manifest.setdefault("variants", [])
        except (OSError, json.JSONDecodeError):
            pass

    known = {v.get("filename") for v in manifest["variants"]}
    for deck in sorted(source.glob(f"WSR_{start}_{end}*.pptx")):
        match = DECK_RE.match(deck.name)
        if not match or deck.name in known:
            continue
        modified = datetime.fromtimestamp(deck.stat().st_mtime, tz=timezone.utc)
        manifest["variants"].append(
            {
                "variant": int(match.group(3) or "1"),
                "template_id": None,
                "template_name": "Unknown template",
                "filename": deck.name,
                "generated_at": modified.isoformat(),
            }
        )
    for variant in manifest["variants"]:
        old_id = variant.get("template_id")
        if old_id in id_map:
            variant["template_id"] = id_map[old_id]
        deck = source / str(variant.get("filename") or "")
        if deck.is_file() and not variant.get("slide_count"):
            count = _slide_count(deck)
            if count:
                variant["slide_count"] = count
    manifest["variants"].sort(key=lambda v: int(v.get("variant") or 1))
    if not manifest["variants"]:
        return None

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / manifest_path.name
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def plan_migration(source: Path, *, work_dir: Path) -> list[Upload]:
    """Work out what to upload (pure local file inspection, no network)."""
    from app.services import sharepoint_storage as storage

    templates_folder = storage.templates_folder()
    decks_folder = storage.decks_folder()
    data_folder = storage.data_folder()
    plan: list[Upload] = []

    # Templates — stored under the uploaded file's own name
    from app.services.wsr_template_upload_service import (
        safe_remote_stem,
        template_id_from_stem,
    )

    remote_sizes = {
        str(i["name"]): int(i.get("size") or -1)
        for i in storage.list_folder(templates_folder, use_cache=False)
    }
    used_stems: set[str] = set()
    id_map: dict[str, str] = {}

    def claim_stem(original: str, local_size: int) -> str:
        base = safe_remote_stem(original)
        stem, counter = base, 1
        while stem.lower() in used_stems or remote_sizes.get(f"{stem}.pptx", local_size) != local_size:
            counter += 1
            stem = f"{base} ({counter})"
        used_stems.add(stem.lower())
        return stem

    def read_original(meta: Path, default: str) -> str:
        if meta.is_file():
            try:
                value = json.loads(meta.read_text(encoding="utf-8")).get("original_filename")
                if value:
                    return str(value)
            except (OSError, json.JSONDecodeError, AttributeError):
                pass
        return default

    templates_dir = source / "wsr_templates"
    saved = sorted(templates_dir.glob("*.pptx")) if templates_dir.is_dir() else []
    for pptx in saved:
        if not TEMPLATE_ID_RE.match(pptx.stem):
            continue
        meta = pptx.with_suffix(".json")
        stem = claim_stem(read_original(meta, pptx.name), pptx.stat().st_size)
        id_map[pptx.stem] = template_id_from_stem(stem)
        plan.append(Upload(pptx, templates_folder, f"{stem}.pptx", "template"))
        if meta.is_file():
            plan.append(Upload(meta, templates_folder, f"{stem}.json", "template-meta"))

    legacy = source / LEGACY_TEMPLATE
    if not saved and legacy.is_file():
        legacy_meta = source / LEGACY_TEMPLATE_META
        original = read_original(legacy_meta, legacy.name)
        stem = claim_stem(original, legacy.stat().st_size)
        plan.append(Upload(legacy, templates_folder, f"{stem}.pptx", "template"))
        work_dir.mkdir(parents=True, exist_ok=True)
        meta_file = work_dir / f"{stem}.json"
        meta_file.write_text(
            json.dumps(
                {
                    "original_filename": original,
                    "saved_at": datetime.fromtimestamp(
                        legacy.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        plan.append(Upload(meta_file, templates_folder, f"{stem}.json", "template-meta"))

    # Decks, sidecars, validation
    weeks: set[tuple[str, str]] = set()
    for path in sorted(source.glob("WSR_*")):
        if path.is_file():
            if DECK_RE.match(path.name):
                weeks.add((DECK_RE.match(path.name).group(1), DECK_RE.match(path.name).group(2)))
                plan.append(Upload(path, decks_folder, path.name, "deck"))
            elif CONTENT_RE.match(path.name) or PREVIEW_RE.match(path.name):
                plan.append(Upload(path, data_folder, path.name, "sidecar"))
            elif REPORT_RE.match(path.name):
                stem = REPORT_RE.match(path.name).group(1)
                plan.append(Upload(path, f"{data_folder}/{stem}_validation", path.name, "validation"))
        elif path.is_dir():
            match = VALIDATION_DIR_RE.match(path.name)
            if match:
                folder = f"{data_folder}/{match.group(1)}_validation"
                for image in sorted(path.glob("slide_*_*.png")):
                    if ANNOTATION_RE.match(image.name):
                        plan.append(Upload(image, folder, image.name, "validation"))

    for start, end in sorted(weeks):
        manifest = _build_manifest_file(source, start, end, work_dir, id_map)
        if manifest is not None:
            plan.append(Upload(manifest, data_folder, manifest.name, "manifest"))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=None, help="Old output folder (default: <backend>/output)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded")
    parser.add_argument("--overwrite", action="store_true", help="Re-upload files that already exist remotely")
    args = parser.parse_args()

    from app.paths import LEGACY_OUTPUT_DIR, WORK_DIR
    from app.services import sharepoint_storage as storage

    source = Path(args.source).resolve() if args.source else LEGACY_OUTPUT_DIR
    if not source.is_dir():
        print(f"Nothing to migrate: {source} does not exist.")
        return 0
    try:
        storage.require_storage()
    except storage.StorageError as exc:
        print(f"Error: {exc}")
        return 1

    plan = plan_migration(source, work_dir=WORK_DIR / "_migration")
    if not plan:
        print(f"No WSR files found in {source}.")
        return 0

    remote_sizes: dict[str, dict[str, int]] = {}
    uploaded = skipped = failed = 0
    for upload in plan:
        if upload.folder not in remote_sizes:
            try:
                remote_sizes[upload.folder] = {
                    str(i["name"]): int(i.get("size") or -1)
                    for i in storage.list_folder(upload.folder, use_cache=False)
                }
            except storage.StorageError as exc:
                print(f"Error listing {upload.folder}: {exc}")
                return 1
        exists = remote_sizes[upload.folder].get(upload.remote_name)
        if (
            not args.overwrite
            and upload.kind != "manifest"
            and exists == upload.local.stat().st_size
        ):
            skipped += 1
            print(f"skip    {upload.folder}/{upload.remote_name} (already there)")
            continue
        if args.dry_run:
            print(f"would upload [{upload.kind}] {upload.local.name} -> {upload.folder}/{upload.remote_name}")
            continue
        try:
            storage.upload_file(upload.local, upload.folder, upload.remote_name)
            uploaded += 1
            print(f"uploaded [{upload.kind}] {upload.folder}/{upload.remote_name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAILED   {upload.folder}/{upload.remote_name}: {exc}")

    print(f"\nDone. uploaded={uploaded} skipped={skipped} failed={failed}" + (" (dry run)" if args.dry_run else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
