from __future__ import annotations

import logging

from app.infrastructure.repositories.dashboard_repository import (
    DashboardRepository,
)

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Dashboard business logic.

    Responsible for transforming repository
    results into API-friendly responses.
    """

    @classmethod
    def get_summary(cls) -> dict:
        """
        Retrieve dashboard summary.
        """

        logger.info(
            "Loading dashboard summary."
        )

        (
            total_rows,
            total_location,
            total_ulp,
        ) = DashboardRepository.get_summary()

        return {
            "total_rows": total_rows,
            "total_location": total_location,
            "total_ulp": total_ulp,
        }

    @classmethod
    def get_kpi(cls) -> dict:
        """
        Retrieve dashboard KPI.
        """

        logger.info(
            "Loading dashboard KPI."
        )

        (
            total_customer,
            suspect_customer,
        ) = DashboardRepository.get_kpi()

        return {
            "total_customer": total_customer,
            "suspect_customer": suspect_customer,
        }

    @classmethod
    def get_top_unit(
        cls,
    ) -> list[dict]:
        """
        Retrieve Top ULP based on
        total customers.
        """

        logger.info(
            "Loading top unit."
        )

        rows = DashboardRepository.get_top_unit()

        return [
            {
                "unitup": row[0],
                "total_customer": row[1],
                "total_suspect": row[2],
            }
            for row in rows
        ]

    @classmethod
    def get_location_distribution(
        cls,
    ) -> list[dict]:
        """
        Retrieve customer distribution
        by location.
        """

        logger.info(
            "Loading location distribution."
        )

        rows = (
            DashboardRepository.get_location_distribution()
        )

        return [
            {
                "location_name": row[0],
                "total_customer": row[1],
            }
            for row in rows
        ]