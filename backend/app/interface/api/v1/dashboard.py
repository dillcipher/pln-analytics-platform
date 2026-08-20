from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.application.dashboard.dashboard_service import (
    DashboardService,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/summary")
async def get_summary():

    try:

        logger.info(
            "Dashboard summary requested."
        )

        return {
            "success": True,
            "message": (
                "Dashboard summary retrieved successfully."
            ),
            "data": DashboardService.get_summary(),
        }

    except Exception as e:

        logger.exception(
            "Failed to retrieve dashboard summary."
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/kpi")
async def get_kpi():

    try:

        logger.info(
            "Dashboard KPI requested."
        )

        return {
            "success": True,
            "message": (
                "Dashboard KPI retrieved successfully."
            ),
            "data": DashboardService.get_kpi(),
        }

    except Exception as e:

        logger.exception(
            "Failed to retrieve dashboard KPI."
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/top-unit")
async def get_top_unit():

    try:

        logger.info(
            "Dashboard top unit requested."
        )

        return {
            "success": True,
            "message": (
                "Top unit retrieved successfully."
            ),
            "data": DashboardService.get_top_unit(),
        }

    except Exception as e:

        logger.exception(
            "Failed to retrieve top unit."
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/location-distribution")
async def get_location_distribution():

    try:

        logger.info(
            "Dashboard location distribution requested."
        )

        return {
            "success": True,
            "message": (
                "Location distribution retrieved successfully."
            ),
            "data": DashboardService.get_location_distribution(),
        }

    except Exception as e:

        logger.exception(
            "Failed to retrieve location distribution."
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )