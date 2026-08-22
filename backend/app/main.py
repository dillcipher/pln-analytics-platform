"""PLN Analytics Platform — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.database.warehouse import Warehouse
from app.etl.detector.dlpd_month_fallback_patch import install_dlpd_month_fallback_patch
from app.etl.detector.dlpd_transformer_patch import install_dlpd_transformer_patch
from app.etl.detector.streaming_month_resolver_patch import install_streaming_month_resolver_patch
from app.etl.merger.idpel_normalization_patch import install_idpel_normalization_patch
from app.etl.merger.streaming_dlpd_merger_patch import install_streaming_dlpd_merger_patch
from app.etl.runtime_guard import install_runtime_guards
from app.infrastructure.duckdb.dlpd_query_guard import install_dlpd_query_guard
from app.infrastructure.storage.processed_storage import hydrate_processed_data
from app.application.etl.etl_orchestrator import ETLOrchestrator

install_dlpd_transformer_patch()
install_streaming_month_resolver_patch()
install_idpel_normalization_patch()
install_streaming_dlpd_merger_patch()
install_dlpd_month_fallback_patch()
install_runtime_guards()
install_dlpd_query_guard()

_ETL_ACTIVE_JOBS: set[str] = set()
_ETL_ACTIVE_LOCK = threading.Lock()
_ORIGINAL_ETL_PROCESS = ETLOrchestrator.process.__func__


def _deduplicated_etl_process(cls, job_folder: Path):
    job_id = str(job_folder.name or "").strip()
    if not job_id:
        raise ValueError("ETL job folder does not contain a valid job_id.")

    with _ETL_ACTIVE_LOCK:
        if job_id in _ETL_ACTIVE_JOBS:
            logging.getLogger(__name__).warning(
                "ETL DUPLICATE TRIGGER IGNORED | JOB=%s",
                job_id,
            )
            return {
                "success": True,
                "job_id": job_id,
                "status": "ALREADY_RUNNING",
                "message": "ETL job is already running in this instance.",
            }
        _ETL_ACTIVE_JOBS.add(job_id)

    try:
        return _ORIGINAL_ETL_PROCESS(cls, job_folder)
    finally:
        with _ETL_ACTIVE_LOCK:
            _ETL_ACTIVE_JOBS.discard(job_id)


ETLOrchestrator.process = classmethod(_deduplicated_etl_process)

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

    hydrated = hydrate_processed_data()
    logger.info("Hydrated processed artifacts: %s", hydrated)

    try:
        Warehouse.refresh_tables()
        logger.info("Startup warehouse refresh completed.")
    except Exception:
        logger.exception("Startup warehouse refresh failed; continuing startup.")

    # Recover exactly one unfinished durable job in the background. The
    # recovery implementation is bounded to one job and uses the same ETL
    # memory gate/deduplication path as normal processing.
    auto_recover = os.getenv(
        "AUTO_RECOVER_ETL_ON_STARTUP",
        "1",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if auto_recover:
        try:
            from app.application.etl.startup_recovery_once import recover_one_pending_job

            async def _explicit_recovery():
                try:
                    result = await recover_one_pending_job()
                    logger.warning("STARTUP RECOVERY RESULT | %s", result)
                except Exception:
                    logger.exception("STARTUP RECOVERY FAILED")

            asyncio.create_task(_explicit_recovery())
            logger.info("Startup ETL recovery scheduled: one eligible durable job.")
        except Exception:
            logger.exception("Could not schedule startup recovery.")
    else:
        logger.info("Startup ETL recovery disabled by AUTO_RECOVER_ETL_ON_STARTUP.")

    logger.info("Application startup complete.")
    logger.info("=" * 80)
