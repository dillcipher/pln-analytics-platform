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
from app.etl.detector.dlpd_transformer_patch import install_dlpd_transformer_patch
from app.etl.detector.streaming_month_resolver_patch import install_streaming_month_resolver_patch
from app.etl.merger.streaming_dlpd_merger_patch import install_streaming_dlpd_merger_patch
from app.etl.runtime_guard import install_runtime_guards
from app.infrastructure.storage.processed_storage import hydrate_processed_data
from app.application.etl.etl_orchestrator import ETLOrchestrator

install_dlpd_transformer_patch()
install_streaming_month_resolver_patch()
install_streaming_dlpd_merger_patch()
install_runtime_guards()

# A single deployment can receive the same job from multiple paths:
# upload completion, frontend polling/retry, or manual recovery.  The
# runtime guard serializes ETL for memory safety, but serialization alone
# would make a duplicate request run the same job twice.  Keep a process-
# local active-job registry so a duplicate trigger becomes a harmless no-op.
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

    # Restore already-processed parquet artifacts before opening DuckDB.
    # This is lightweight compared with re-reading the source workbooks.
    hydrated = hydrate_processed_data()
    logger.info("Hydrated processed artifacts: %s", hydrated)

    tables: set[str] = set()
    try:
        Warehouse.refresh_tables()
        tables = set(Warehouse.list_tables())
        logger.info("Startup warehouse refresh completed.")
    except Exception:
        logger.exception("Startup warehouse refresh failed; continuing startup.")

    # ==============================================================
    # BOUNDED SELF-HEALING RECOVERY
    # ==============================================================
    #
    # The previous implementation either recovered every unfinished job
    # during startup (which could OOM the instance) or disabled recovery
    # completely (which left a fresh deployment with zero dashboard data).
    #
    # Correct behavior:
    #   1. Hydrate durable processed parquet.
    #   2. Refresh DuckDB views.
    #   3. If the DLPD warehouse is still missing, recover ONE durable job
    #      in the background.
    #   4. Never block FastAPI startup and never fan out across all jobs.
    #
    # One-job recovery is enough for the normal deployment model where the
    # uploaded workbook is the durable source for the whole DLPD dataset.
    # If another unfinished job remains, it can be recovered on the next
    # restart without creating a simultaneous memory spike.
    required_data_tables = {
        "fact_dlpd_prabayar",
        "fact_dlpd_pascabayar",
    }

    if not required_data_tables.issubset(tables):
        try:
            from app.application.etl.startup_recovery_once import (
                recover_one_pending_job,
            )

            async def _bounded_recovery():
                try:
                    result = await recover_one_pending_job()
                    logger.warning(
                        "BOUNDED STARTUP RECOVERY COMPLETED | %s",
                        result,
                    )
                except Exception:
                    logger.exception(
                        "BOUNDED STARTUP RECOVERY FAILED",
                    )

            asyncio.create_task(_bounded_recovery())
            logger.warning(
                "DLPD warehouse is incomplete; one durable ETL job was queued for background recovery."
            )
        except Exception:
            logger.exception(
                "Could not schedule bounded startup recovery."
            )
    else:
        logger.info(
            "DLPD warehouse is present; startup ETL recovery is not required."
        )

    logger.info("=" * 80)
