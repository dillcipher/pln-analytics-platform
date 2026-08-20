from __future__ import annotations

from app.infrastructure.repositories.dashboard_repository import (
    DashboardRepository,
)


class DashboardService:

    @classmethod
    def get_summary(cls):

        result = DashboardRepository.get_summary()

        return {

            "total_rows": result[0],

            "total_location": result[1],

            "total_ulp": result[2],

        }

    @classmethod
    def get_kpi(cls):

        result = DashboardRepository.get_kpi()

        return {

            "total_customer": result[0],

            "suspect_customer": result[1],

        }