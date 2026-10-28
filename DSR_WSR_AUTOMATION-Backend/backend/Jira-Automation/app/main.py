import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.dsr import router as dsr_router
from app.api.routes.employees import router as employees_router
from app.api.routes.stories import router as stories_router
from app.api.routes.tracks import router as tracks_router
from app.api.routes.wsr import router as wsr_router
from app.paths import ensure_output_dir
from app.services.sharepoint_storage import StorageError, StorageNotConfiguredError
from app.services.work_cache import purge_stale_work_cache


@asynccontextmanager
async def lifespan(_: FastAPI):
    # SharePoint is the source of truth; the local work dir is only a scratch cache,
    # so old cached files are deleted on every start.
    try:
        purge_stale_work_cache()
        ensure_output_dir()
    except Exception:  # noqa: BLE001 - never block startup on cache housekeeping
        logging.getLogger(__name__).exception("Work cache purge failed")
    yield


app = FastAPI(
    title="DSR/WSR Automation API",
    description="API for Daily Status Report views by team and track.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StorageNotConfiguredError)
async def _storage_not_configured_handler(_: Request, exc: StorageNotConfiguredError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(StorageError)
async def _storage_error_handler(_: Request, exc: StorageError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.include_router(auth_router)
app.include_router(dsr_router)
app.include_router(stories_router)
app.include_router(employees_router)
app.include_router(wsr_router)
app.include_router(tracks_router)


@app.get("/health")
def health() -> dict[str, str]:
    from app.rendering.factory import describe_active_renderer

    return {"status": "ok", "slide_renderer": describe_active_renderer()}
