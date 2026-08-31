"""Background WSR generation jobs so the API stays responsive."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.database import SessionLocal
from app.services.wsr_service import generate_wsr_deck

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class WsrJob:
    job_id: str
    start_date: date
    end_date: date
    template_id: str
    status: JobStatus = "queued"
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


_lock = threading.Lock()
_jobs: dict[str, WsrJob] = {}


def job_id_for_range(start_date: date, end_date: date) -> str:
    return f"{start_date.isoformat()}_{end_date.isoformat()}"


def get_job(start_date: date, end_date: date) -> WsrJob | None:
    job_id = job_id_for_range(start_date, end_date)
    with _lock:
        return _jobs.get(job_id)


def start_wsr_job(
    *,
    start_date: date,
    end_date: date,
    template_id: str,
    force: bool = False,
) -> WsrJob:
    """Queue WSR generation on a background thread."""
    job_id = job_id_for_range(start_date, end_date)

    with _lock:
        existing = _jobs.get(job_id)
        if existing and existing.status in {"queued", "running"} and not force:
            return existing
        job = WsrJob(
            job_id=job_id,
            start_date=start_date,
            end_date=end_date,
            template_id=template_id,
        )
        _jobs[job_id] = job

    def _run() -> None:
        with _lock:
            job.status = "running"
            job.started_at = time.time()
            job.error = None
            job.result = None

        db = SessionLocal()
        try:
            result = generate_wsr_deck(
                db,
                start_date=start_date,
                end_date=end_date,
                template_id=job.template_id,
            )
            with _lock:
                job.status = "completed"
                job.result = result
                job.finished_at = time.time()
        except Exception as exc:
            with _lock:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = time.time()
        finally:
            db.close()

    threading.Thread(target=_run, name=f"wsr-{job_id}", daemon=True).start()
    return job
