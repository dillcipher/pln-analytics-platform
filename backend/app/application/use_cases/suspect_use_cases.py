"""
Suspect Analytics use-cases.

Covers:
    - Available Suspect / ANEV months
    - Main suspect records
    - Summary / classification
    - Detail records
    - Detail trend
    - Classification summary
    - Repeat / repeated customer analysis
    - Combined Suspect Analytics dashboard
"""

from __future__ import annotations

from typing import Any

from app.domain.entities import MonthOption, PageResult
from app.domain.repositories import SuspectRepository


class GetSuspectMonths:
    """Return available Suspect / ANEV months."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(self) -> list[MonthOption]:
        return self._repository.get_available_months()


class GetSuspectMain:
    """Return paginated main suspect records."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(
        self,
        month_key: str,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> PageResult:
        return self._repository.get_main(
            month_key,
            page,
            page_size,
            search,
        )


class GetSuspectSummary:
    """Return suspect summary using repository classification rules."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self._repository.get_summary(
            month_key,
            filters or {},
        )


class GetSuspectDetail:
    """Return paginated suspect detail records."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(
        self,
        month_key: str,
        filters: dict[str, Any] | None,
        page: int,
        page_size: int,
    ) -> PageResult:
        return self._repository.get_detail(
            month_key,
            filters or {},
            page,
            page_size,
        )


class GetSuspectDetailTrend:
    """Return historical trend information for a selected location."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(
        self,
        month_key: str,
        location_code: str,
    ) -> dict[str, Any]:
        return self._repository.get_detail_trend(
            month_key,
            location_code,
        )


class GetSuspectClassification:
    """Return suspect counts grouped by SUSPECT_NAME."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self._repository.get_classification_summary(
            month_key,
            filters or {},
        )


class GetSuspectRepeat:
    """Return repeated suspect / customer information."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(self, month_key: str) -> dict[str, Any]:
        return self._repository.get_repeat_summary(
            month_key,
        )


class GetSuspectAnalytics:
    """Return complete analytics required by the Suspect dashboard."""

    def __init__(self, repository: SuspectRepository):
        self._repository = repository

    def execute(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filters = filters or {}

        # Repository-level dashboard is the single compatibility entry point.
        # It returns the same analytical sections consumed by the frontend.
        return self._repository.get_dashboard(
            month_key,
            filters,
        )
