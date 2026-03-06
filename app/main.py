"""BlackRoad API — Main FastAPI Application (port 8788)."""

import time
from time import perf_counter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import router as v1_router
from app.api.v1.railway import router as railway_router
from app.api.v1.github import router as github_router
from app.api.v1.roadchain import router as roadchain_router
from app.api.v1.live_feed import router as live_feed_router
from app.api.v1.cloudflare import router as cloudflare_router
from app.api.v1.digitalocean import router as digitalocean_router
from app.core.logging import configure_logging
from app.core.settings import settings
from app.workers.sample_task import celery_app
from app.database import init_db


def create_app() -> FastAPI:
    configure_logging()
    init_db(settings.db_path)

    application = FastAPI(
        title="BlackRoad OS API",
        description="REST API for BlackRoad OS — agents, tasks, memory, chat, and integrations",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.state.settings = settings
    application.state.celery_app = celery_app
    application.state.start_time = perf_counter()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @application.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    @application.get("/health", tags=["health"])
    async def health_check():
        return {
            "status": "ok",
            "version": application.version,
            "timestamp": int(time.time()),
        }

    # Core API routes
    application.include_router(v1_router, prefix="/v1")

    # Integration routes (issues #2-#7)
    application.include_router(railway_router, prefix="/v1")
    application.include_router(github_router, prefix="/v1")
    application.include_router(roadchain_router, prefix="/v1")
    application.include_router(live_feed_router, prefix="/v1")
    application.include_router(cloudflare_router, prefix="/v1")
    application.include_router(digitalocean_router, prefix="/v1")

    return application


app = create_app()
__all__ = ["app"]
