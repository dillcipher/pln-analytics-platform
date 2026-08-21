"""PLN Analytics Platform — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.etl.startup_recovery import recover_pending_jobs
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.database.warehouse import Warehouse
from app.etl.detector.streaming_month_resolver_patch import (
    install_streaming_month_resolver_patch,
)
from app.etl.runtime_guard import install_runtime_guards
from app.infrastructure.storage.processed_storage import hydrate_processed_data

# Install all low-memory guards before importing the API router. This ensures
# every upload/ETL path uses the same serialized ETL and stable S3 transfer.
install_streaming_month_resolver_patch()
install_runtime_guards()

from app.interface.api.v1.router import api_v1_router  # noqa: E402

settings = get_settings()
configure_logging(settings.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Enterprise Analytics Platform for PLN. Modules: Upload Center, "
        "Executive Dashboard, DLPD Monitoring, Suspect Analytics, and Warehouse Management."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://([a-zA-Z0-9-]+\.)*vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "application": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@app.on_event("startup")
async def on_startup():
    logger.info("=" * 80)
    logger.info("%s", settings.APP_NAME)
    logger.info("Environment : %s", settings.ENVIRONMENT)
    logger.info("Processed Data : %s", settings.DATA_PROCESSED_DIR)

    hydrated = hydrate_processed_data()
    logger.info("Hydrated processed artifacts: %s", hydrated)

    try:
        Warehouse.refresh_tables()
        logger.info("Startup warehouse refresh completed.")
    except Exception:
        logger.exception("Startup warehouse refresh failed; continuing startup.")

    # Durable processed artifacts are hydrated before the initial warehouse
    # refresh. Any upload that was interrupted after reaching durable storage
    # is then recovered in the background and sent through the exact same ETL
    # path used by a fresh upload. The runtime guard serializes the heavy work
    # so recovery cannot start several large Excel jobs concurrently.
    logger.info("Scheduling startup recovery of unfinished durable uploads.")
    asyncio.create_task(_startup_recovery_task())

    if not settings.DATA_PROCESSED_DIR.exists():
        logger.warning(
            "Processed data directory not found. Upload and run the ETL pipeline "
            "to populate the dashboard."
        )

    logger.info("=" * 80)


async def _startup_recovery_task() -> None:
    try:
        result = await recover_pending_jobs()
        logger.info("Startup ETL recovery result: %s", result)
    except Exception:
        # Recovery must never prevent the API from becoming available.
        logger.exception("Startup ETL recovery task failed.")
