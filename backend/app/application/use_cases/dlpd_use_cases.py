from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.entities import (
    DlpdCustomerDetail,
    DlpdDashboard,
    DlpdDashboardUlp,
    MonthOption,
    PageResult,
)
from app.domain.repositories import (
    CustomerType,
    DlpdFilters,
    DlpdRepository,
)


# ==========================================================
# COMMON HELPERS
# ==========================================================

def _normalize_idpel(idpel: str | None) -> str:
    """
    Normalize IDPEL before passing it to the repository.

    Excel/Pandas can expose the same logical IDPEL in different forms,
    for example:

        171002615379
        171002615379.0
        1.71002615379E+11

    The use-case layer normalizes only formatting artifacts. It does
    not alter ordinary string IDs or intentionally preserve/strip
    leading zeros.
    """
    if idpel is None:
        return ""

    value = str(idpel).strip()

    if not value:
        return ""

    # Excel/Pandas integer suffix: "123456.0"
    if value.endswith(".0") and value[:-2].isdigit():
        return value[:-2]

    # Scientific notation representing an integer IDPEL.
    if "e" in value.lower():
        try:
            number = Decimal(value)

            if number == number.to_integral_value():
                return format(
                    number.quantize(Decimal("1")),
                    "f",
                )
        except (InvalidOperation, ValueError):
            pass

    return value


def _normalize_month(
    month_key: str | None,
) -> str | None:
    """
    Normalize the frontend month contract.

    All-month values are represented internally as None.

    Examples:

        None               -> None
        ""                 -> None
        "__ALL_MONTHS__"   -> None
        "semua bulan"      -> None
        "2026-06"          -> "202606"
        "2026/06"          -> "202606"
        "202606"           -> "202606"

    Concrete month keys are otherwise passed through unchanged.
    """
    if month_key is None:
        return None

    value = str(month_key).strip()

    if not value:
        return None

    normalized = value.lower()

    if normalized in {
        "__all_months__",
        "__all_month__",
        "all",
        "all_months",
        "all_month",
        "all-months",
        "all-month",
        "all months",
        "all month",
        "semua",
        "semua_bulan",
        "semua bulan",
        "semua-bulan",
        "semua_bulan_data",
    }:
        return None

    compact = (
        value
        .replace("-", "")
        .replace("/", "")
        .replace(" ", "")
    )

    if len(compact) == 6 and compact.isdigit():
        return compact

    return value


def _safe_positive_int(
    value: int,
    default: int,
) -> int:
    """
    Convert an incoming pagination/limit value into a positive integer
    without allowing invalid values to break the use-case layer.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return max(parsed, 1)


# ==========================================================
# MONTH
# ==========================================================

class GetDlpdMonths:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
    ) -> list[MonthOption]:

        result = self._repository.get_available_months(
            customer_type,
        )

        if result is None:
            return []

        return list(result)


# ==========================================================
# FILTER
# ==========================================================

class GetDlpdFilterOptions:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        month_key: str | None,
    ) -> dict[str, list[str]]:

        result = self._repository.get_filter_options(
            customer_type,
            _normalize_month(month_key),
        )

        if result is None:
            return {}

        return result


# ==========================================================
# DASHBOARD KPI
# ==========================================================

class GetDlpdDashboard:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        month_key: str | None,
        filters: DlpdFilters,
    ) -> DlpdDashboard:

        return self._repository.get_dashboard(
            customer_type,
            _normalize_month(month_key),
            filters,
        )


# ==========================================================
# DASHBOARD ULP
# ==========================================================

class GetDlpdDashboardUlp:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        month_key: str | None,
        filters: DlpdFilters,
    ) -> list[DlpdDashboardUlp]:

        result = self._repository.get_dashboard_ulp(
            customer_type,
            _normalize_month(month_key),
            filters,
        )

        if result is None:
            return []

        return list(result)


# ==========================================================
# CUSTOMER LIST
# ==========================================================

class GetDlpdCustomers:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        month_key: str | None,
        filters: DlpdFilters,
        page: int,
        page_size: int,
    ) -> PageResult:

        safe_page = _safe_positive_int(
            page,
            default=1,
        )

        safe_page_size = _safe_positive_int(
            page_size,
            default=100,
        )

        return self._repository.get_customers(
            customer_type,
            _normalize_month(month_key),
            filters,
            safe_page,
            safe_page_size,
        )


# ==========================================================
# CUSTOMER DETAIL
# ==========================================================

class GetDlpdCustomerDetail:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        idpel: str,
        month_key: str | None,
    ) -> DlpdCustomerDetail | None:

        normalized_idpel = _normalize_idpel(idpel)

        if not normalized_idpel:
            return None

        return self._repository.get_customer_detail(
            customer_type,
            normalized_idpel,
            _normalize_month(month_key),
        )


# ==========================================================
# EXPORT
# ==========================================================

class ExportDlpdCustomers:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        month_key: str | None,
        filters: DlpdFilters,
    ) -> list[dict]:

        result = self._repository.export_customers(
            customer_type,
            _normalize_month(month_key),
            filters,
        )

        if result is None:
            return []

        return list(result)


# ==========================================================
# MAP POINTS
# ==========================================================

class GetDlpdMapPoints:

    def __init__(
        self,
        repository: DlpdRepository,
    ):
        self._repository = repository

    def execute(
        self,
        customer_type: CustomerType,
        month_key: str | None,
        filters: DlpdFilters | None = None,
        limit: int = 100_000,
    ) -> dict[str, Any]:

        safe_limit = min(
            _safe_positive_int(
                limit,
                default=100_000,
            ),
            100_000,
        )

        result = self._repository.get_map_points(
            customer_type=customer_type,
            month_key=_normalize_month(month_key),
            filters=filters,
            limit=safe_limit,
        )

        if result is None:
            return {
                "total": 0,
                "location_matched": 0,
                "mapped": 0,
                "unmapped": 0,
                "points": [],
            }

        return result
