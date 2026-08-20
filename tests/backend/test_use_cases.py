"""
Use-case tests, run against FAKE in-memory repositories (not DuckDB).

This is the payoff of Clean Architecture's dependency-inversion: these
tests prove the business logic (pagination math, filter pass-through,
month lookups) is correct without needing a database, without needing
DuckDB installed, and without booting FastAPI. The real DuckDB
repositories are exercised separately by
`tests/backend/test_duckdb_repositories.py` (integration-level, needs
`pip install duckdb pyarrow`).

Run directly with:  python -m tests.backend.test_use_cases
(also fully compatible with `pytest tests/backend/test_use_cases.py`)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.application.use_cases.dlpd_use_cases import GetDlpdCustomers, GetDlpdFilterOptions
from app.application.use_cases.executive_use_cases import GetExecutiveKpis
from app.application.use_cases.suspect_use_cases import GetSuspectMain, GetSuspectSummary
from app.domain.entities import KpiSet, MonthOption, PageResult


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class FakeExecutiveRepository:
    def get_available_months(self) -> list[MonthOption]:
        return [MonthOption("202607", "Juli 2026"), MonthOption("202606", "Juni 2026")]

    def get_kpis(self, month_key: str) -> KpiSet | None:
        if month_key != "202607":
            return None
        return KpiSet(
            month_key="202607", total_customers=556, total_suspects=507,
            total_normal=115, total_findings=65, remaining_inspection=327,
            progress_pct=35.5, hit_rate_pct=36.11,
        )

    def get_chart_data(self, month_key: str) -> dict:
        return {"bar_by_unitap": [{"label": "UP3 METRO", "value": 120}]}


class FakeDlpdRepository:
    def __init__(self):
        self._customers = [
            {"IDPEL": "511700000001", "NAMA": "Budi Santoso", "UNITUP": "ULP METRO", "DLPD": 1},
            {"IDPEL": "511700000002", "NAMA": "Siti Wijaya", "UNITUP": "ULP KEDATON", "DLPD": 0},
            {"IDPEL": "511700000003", "NAMA": "Andi Saputra", "UNITUP": "ULP METRO", "DLPD": 2},
        ]

    def get_available_months(self):
        return [MonthOption("202607", "Juli 2026")]

    def get_filter_options(self, month_key):
        return {"unitupi": ["UID LAMPUNG"], "unitap": ["UP3 METRO"], "unitup": ["ULP METRO", "ULP KEDATON"], "status": ["NORMAL", "SUSPECT"], "tariff": ["R1", "R2"]}

    def get_dashboard_ulp(self, month_key, filters):
        return [{"unitup": "ULP METRO", "total_customers": 2}]

    def get_customers(self, month_key, filters, page, page_size) -> PageResult:
        filtered = self._customers
        if filters.get("unitup"):
            filtered = [c for c in filtered if c["UNITUP"] == filters["unitup"]]
        start = (page - 1) * page_size
        page_items = filtered[start:start + page_size]
        return PageResult(items=page_items, total_rows=len(filtered), page=page, page_size=page_size)

    def get_customer_detail(self, idpel, month_key):
        for c in self._customers:
            if c["IDPEL"] == idpel:
                return c
        return None


class FakeSuspectRepository:
    def get_available_months(self):
        return [MonthOption("202607", "Juli 2026")]

    def get_main(self, month_key, page, page_size, search) -> PageResult:
        rows = [
            {"suspect_name": "OVER VOLTAGE BY INSTANT", "pelanggan": 70, "frekuensi": 71},
            {"suspect_name": "UNDER VOLTAGE BY INSTANT", "pelanggan": 65, "frekuensi": 66},
        ]
        if search:
            rows = [r for r in rows if search.upper() in r["suspect_name"]]
        start = (page - 1) * page_size
        return PageResult(items=rows[start:start + page_size], total_rows=len(rows), page=page, page_size=page_size)

    def get_summary(self, month_key, filters):
        return [{"LOCATION_CODE": "511700000001", "GRAND_TOTAL": 3}]

    def get_detail(self, month_key, filters, page, page_size):
        return PageResult(items=[], total_rows=0, page=page, page_size=page_size)

    def get_detail_trend(self, month_key, location_code):
        return {"location_code": location_code, "voltage_l1": [], "stats": {}}


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_get_executive_kpis_found():
    use_case = GetExecutiveKpis(FakeExecutiveRepository())
    result = use_case.execute("202607")
    assert result is not None
    assert result.total_customers == 556
    assert result.hit_rate_pct == 36.11


def test_get_executive_kpis_unknown_month_returns_none():
    use_case = GetExecutiveKpis(FakeExecutiveRepository())
    assert use_case.execute("209912") is None


def test_dlpd_customers_pagination():
    use_case = GetDlpdCustomers(FakeDlpdRepository())
    page1 = use_case.execute("202607", {}, page=1, page_size=2)
    assert page1.total_rows == 3
    assert len(page1.items) == 2
    assert page1.total_pages == 2

    page2 = use_case.execute("202607", {}, page=2, page_size=2)
    assert len(page2.items) == 1


def test_dlpd_customers_filter_by_unitup():
    use_case = GetDlpdCustomers(FakeDlpdRepository())
    result = use_case.execute("202607", {"unitup": "ULP METRO"}, page=1, page_size=10)
    assert result.total_rows == 2
    assert all(c["UNITUP"] == "ULP METRO" for c in result.items)


def test_dlpd_filter_options_shape():
    use_case = GetDlpdFilterOptions(FakeDlpdRepository())
    options = use_case.execute("202607")
    assert set(options.keys()) == {"unitupi", "unitap", "unitup", "status", "tariff"}


def test_suspect_main_search():
    use_case = GetSuspectMain(FakeSuspectRepository())
    result = use_case.execute("202607", page=1, page_size=10, search="UNDER")
    assert result.total_rows == 1
    assert result.items[0]["suspect_name"] == "UNDER VOLTAGE BY INSTANT"


def test_suspect_summary_has_grand_total():
    use_case = GetSuspectSummary(FakeSuspectRepository())
    rows = use_case.execute("202607", {})
    assert rows[0]["GRAND_TOTAL"] == 3


ALL_TESTS = [
    test_get_executive_kpis_found,
    test_get_executive_kpis_unknown_month_returns_none,
    test_dlpd_customers_pagination,
    test_dlpd_customers_filter_by_unitup,
    test_dlpd_filter_options_shape,
    test_suspect_main_search,
    test_suspect_summary_has_grand_total,
]


def main() -> int:
    failures = 0
    for test in ALL_TESTS:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(ALL_TESTS) - failures}/{len(ALL_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
