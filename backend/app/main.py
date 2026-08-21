"""PLN Analytics Platform — FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.database.warehouse import Warehouse
from app.infrastructure.storage.processed_storage import hydrate_processed_data
from app.interface.api.v1.router import api_v1_router

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

# Keep the production Vercel frontend explicitly allowed and also allow
# Vercel deployment/preview subdomains. This prevents an environment-level
# CORS_ORIGINS override from silently breaking the live frontend.
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
def on_startup():
    logger.info("=" * 80)
    logger.info("%s", settings.APP_NAME)
    logger.info("Environment : %s", settings.ENVIRONMENT)
    logger.info("Processed Data : %s", settings.DATA_PROCESSED_DIR)

    # FastAPI Cloud instances are replaceable. Restore durable processed
    # artifacts first, then rebuild/refresh DuckDB tables from the parquet
    # cache so a fresh instance never exposes an empty warehouse merely
    # because its local DuckDB file was missing or stale.
    hydrated = hydrate_processed_data()
    logger.info("Hydrated processed artifacts: %s", hydrated)

    try:
        Warehouse.refresh_tables()
        logger.info("Startup warehouse refresh completed.")
    except Exception:
        # A brand-new deployment legitimately has no processed parquet yet.
        # Do not make the API unhealthy just because there is no dataset.
        logger.exception("Startup warehouse refresh failed; continuing startup.")

    if not settings.DATA_PROCESSED_DIR.exists():
        logger.warning(
            "Processed data directory not found. Upload and run the ETL pipeline "
            "to populate the dashboard."
        )

    logger.info("=" * 80)
