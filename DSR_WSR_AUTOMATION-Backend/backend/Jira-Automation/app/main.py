from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.dsr import router as dsr_router
from app.api.routes.employees import router as employees_router
from app.api.routes.stories import router as stories_router
from app.api.routes.tracks import router as tracks_router
from app.api.routes.wsr import router as wsr_router

app = FastAPI(
    title="DSR/WSR Automation API",
    description="API for Daily Status Report views by team and track.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dsr_router)
app.include_router(stories_router)
app.include_router(employees_router)
app.include_router(wsr_router)
app.include_router(tracks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
