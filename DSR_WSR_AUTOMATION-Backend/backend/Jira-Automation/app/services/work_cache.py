"""Housekeeping for the local work directory (a disposable cache of SharePoint files)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.config import get_settings
from app.paths import OUTPUT_DIR

logger = logging.getLogger(__name__)


def purge_stale_work_cache(
    directory: Path | None = None,
    *,
    max_age_hours: float | None = None,
) -> int:
    """Delete files older than ``max_age_hours`` (default ``WSR_CACHE_MAX_AGE_HOURS``).

    Empty sub-directories are removed afterwards. Returns the number of deleted files.
    ``max_age_hours <= 0`` disables the purge.
    """
    root = Path(directory) if directory is not None else OUTPUT_DIR
    hours = (
        get_settings().wsr_cache_max_age_hours if max_age_hours is None else max_age_hours
    )
    if hours <= 0 or not root.is_dir():
        return 0

    cutoff = time.time() - hours * 3600
    deleted = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
        except OSError as exc:
            logger.debug("Could not delete cached file %s: %s", path, exc)

    # Deepest directories first so parents become empty.
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass

    if deleted:
        logger.info("Purged %d stale cached file(s) from %s", deleted, root)
    return deleted
