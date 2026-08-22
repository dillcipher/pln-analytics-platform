"""PLN Analytics Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.database.warehouse import Warehouse
from app.etl.detector.dlpd_transformer_patch import install_dlpd_transformer_patch
from app.etl.detector.streaming_month_resolver_patch import install_streaming_month_resolver_patch
from app.etl.merger.streaming_dlpd_merger_patch import install_streaming_dlpd_merger_patch
from app.etl.runtime_guard import install_runtime_guards
from app.infrastructure.storage.processed_storage import hydrate_processed_data

install_dlpd_transformer_patch()
install_streaming_month_resolver_patch()
install_streaming_dlpd_merger_patch()
install_runtime_guards()

from app.interface.api.v1.router import api_v1_router  # noqa: E402

settings = get_settings()
configure_logging(settings.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Enterprise Analytics Platform for PLN. Modules: Upload Center, "
        "Executive Dashboard, Suspect Analytics, and Warehouse Management."
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


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Expose deployment readiness without requiring a dashboard request."""
    tables = []
    try:
        tables = Warehouse.list_tables()
    except Exception:
        logger.exception("Readiness warehouse inspection failed.")

    durable_storage = all(
        os.getenv(name, "").strip()
        for name in (
            "S3_ENDPOINT",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
            "S3_BUCKET",
        )
    )

    required_tables = {
        "fact_dlpd_prabayar",
        "fact_dlpd_pascabayar",
        "fact_pengecekan",
        "fact_customer_location",
    }
    warehouse_ready = required_tables.issubset(set(tables))

    return {
        "status": "ready" if durable_storage and warehouse_ready else "degraded",
        "durable_storage": durable_storage,
        "warehouse_ready": warehouse_ready,
        "tables": tables,
    }


@app.on_event("startup")
async def on_startup():
    logger.info("=" * 80)
    logger.info("%s", settings.APP_NAME)
    logger.info("Environment : %s", settings.ENVIRONMENT)
    logger.info("Processed Data : %s", settings.DATA_PROCESSED_DIR)

    # Restore already-processed parquet artifacts before opening DuckDB.
    # This is lightweight compared with re-reading the source workbooks.
    hydrated = hydrate_processed_data()
    logger.info("Hydrated processed artifacts: %s", hydrated)

    try:
        Warehouse.refresh_tables()
        logger.info("Startup warehouse refresh completed.")
    except Exception:
        logger.exception("Startup warehouse refresh failed; continuing startup.")

    # IMPORTANT: do not launch ETL from application startup. FastAPI Cloud
    # instances have a finite memory budget and may restart at any time.
    # Launching every durable unfinished workbook here created an OOM loop and
    # made the API unavailable. New uploads enqueue ETL through the upload
    # pipeline; an existing durable job is explicitly resumable through
    # POST /api/v1/process/{job_id}.
    logger.info(
        "Startup ETL recovery disabled: API readiness is independent of durable job processing."
    )

    logger.info("=" * 80)
