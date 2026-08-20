from __future__ import annotations

from fastapi import APIRouter

from app.interface.api.v1 import (
    auth,
    dashboard,
    data_management,
    datasets,
    dlpd,
    download,
    executive,
    history,
    jobs,
    process,
    suspect,
    upload,
    warehouse,
)

"""
API v1 Router.

All API endpoints are registered here.
"""

api_v1_router = APIRouter(
    prefix="/api/v1",
)

# =====================================================
# Authentication
# =====================================================

api_v1_router.include_router(
    auth.router,
)

# =====================================================
# Upload & ETL
# =====================================================

api_v1_router.include_router(
    upload.router,
)

api_v1_router.include_router(
    process.router,
)

api_v1_router.include_router(
    jobs.router,
)

# =====================================================
# Warehouse
# =====================================================

api_v1_router.include_router(
    warehouse.router,
)

# =====================================================
# Dataset Management
# =====================================================

api_v1_router.include_router(
    datasets.router,
)

api_v1_router.include_router(
    data_management.router,
)

api_v1_router.include_router(
    history.router,
)

api_v1_router.include_router(
    download.router,
)

# =====================================================
# Dashboard
# =====================================================

api_v1_router.include_router(
    dashboard.router,
)

api_v1_router.include_router(
    executive.router,
)

api_v1_router.include_router(
    dlpd.router,
)

api_v1_router.include_router(
    suspect.router,
)