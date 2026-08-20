from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.domain.entities import KpiSet, MonthOption, PageResult


CustomerType = Literal[
    "prabayar",
    "pascabayar",
]


@dataclass(frozen=True)
class DlpdFilters:
    unitupi: str | None = None
    unitap: str | None = None
    unitup: str | None = None
    tariff: str | None = None
    status: str | None = None
    inspection_status: str | None = None
    dlpd_repeat: str | None = None
    kendala: str | None = None
    search_idpel: str | None = None
    search_nama: str | None = None


class ExecutiveRepository(Protocol):
    def get_available_months(self) -> list[MonthOption]: ...
    def get_kpis(self, month_key: str) -> KpiSet | None: ...
    def get_chart_data(self, month_key: str) -> dict[str, Any]: ...
    def get_dashboard(self, month_key: str) -> KpiSet: ...
    def get_filter_options(self, month_key: str | None) -> dict[str, list[str]]: ...


class AnevRepository(Protocol):
    def get_available_months(self) -> list[MonthOption]: ...
    def get_filter_options(self, month_key: str | None) -> dict[str, list[str]]: ...
    def get_dashboard(self, month_key: str, filters: dict[str, Any]) -> dict[str, Any]: ...
    def get_customers(self, month_key: str, filters: dict[str, Any], page: int, page_size: int) -> PageResult: ...
    def get_customer_detail(self, idpel: str, month_key: str) -> dict[str, Any] | None: ...


class SuspectRepository(Protocol):
    def get_available_months(self) -> list[MonthOption]: ...
    def get_filter_options(self, month_key: str | None) -> dict[str, list[str]]: ...

    def get_dashboard(
        self,
        month_key: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]: ...

    def get_main(
        self,
        month_key: str,
        page: int,
        page_size: int,
        search: str | None,
    ) -> PageResult: ...

    def get_summary(
        self,
        month_key: str,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]: ...

    def get_detail(
        self,
        month_key: str,
        filters: dict[str, Any],
        page: int,
        page_size: int,
    ) -> PageResult: ...

    def get_detail_trend(
        self,
        month_key: str,
        location_code: str,
    ) -> dict[str, Any]: ...

    def get_classification_summary(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_repeat_summary(
        self,
        month_key: str,
    ) -> dict[str, Any]: ...

    def get_map_points(
        self,
        month_key: str,
        search: str | None = None,
        unitupi: str | None = None,
        unitap: str | None = None,
        unitup: str | None = None,
        tariff: str | None = None,
        suspect_name: str | None = None,
        repeat_count: int | None = None,
        limit: int = 100_000,
    ) -> dict[str, Any]: ...


class DlpdRepository(Protocol):
    def get_available_months(self, customer_type: CustomerType) -> list[MonthOption]: ...
    def get_filter_options(self, customer_type: CustomerType, month_key: str | None) -> dict[str, list[str]]: ...
    def get_dashboard(self, customer_type: CustomerType, month_key: str, filters: DlpdFilters) -> dict[str, Any]: ...
    def get_dashboard_ulp(self, customer_type: CustomerType, month_key: str, filters: DlpdFilters) -> list[dict[str, Any]]: ...
    def get_customers(self, customer_type: CustomerType, month_key: str, filters: DlpdFilters, page: int, page_size: int) -> PageResult: ...
    def get_customer_detail(self, customer_type: CustomerType, idpel: str, month_key: str) -> dict[str, Any] | None: ...
    def export_customers(self, customer_type: str, month_key: str, filters: DlpdFilters) -> list[dict[str, Any]]: ...
    def get_map_points(self, customer_type: CustomerType, month_key: str, filters: DlpdFilters | None = None, limit: int = 100_000) -> dict[str, Any]: ...
