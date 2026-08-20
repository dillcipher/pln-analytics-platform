"""
Integration tests for the DuckDB-backed repositories, run against REAL
data produced by the ETL sample-data generator (not fakes). Unlike
`test_use_cases.py`, these need `duckdb` and `pyarrow` installed:

    pip install -r backend/requirements.txt
    python -m etl.generate_sample_data --output-dir data/raw --months 202607
    python -m etl.run_etl --input-dir data/raw --output-dir data/processed
    DATA_PROCESSED_DIR=data/processed python -m tests.backend.test_duckdb_repositories

(also runnable via `pytest tests/backend/test_duckdb_repositories.py`
with the same env var / a `backend/.env` pointing at the same data)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# Must be set before app.core.config is imported anywhere (it reads env at import time via get_settings()).
os.environ.setdefault("DATA_PROCESSED_DIR", str(ROOT / "data" / "processed"))

from app.core.config import get_settings  # noqa: E402
from app.infrastructure.duckdb.dlpd_repository import DuckDbDlpdRepository  # noqa: E402
from app.infrastructure.duckdb.executive_repository import DuckDbExecutiveRepository  # noqa: E402
from app.infrastructure.duckdb.suspect_repository import DuckDbSuspectRepository  # noqa: E402


def _first_available_month(months) -> str:
    assert months, "No months found — did you run the ETL against sample data first?"
    return months[0].month_key


def test_executive_kpis_roundtrip():
    repo = DuckDbExecutiveRepository()
    months = repo.get_available_months()
    month = _first_available_month(months)
    kpis = repo.get_kpis(month)
    assert kpis is not None
    assert kpis.total_customers > 0


def test_dlpd_customers_pagination_and_filters():
    repo = DuckDbDlpdRepository()
    month = _first_available_month(repo.get_available_months())
    page1 = repo.get_customers(month, {}, page=1, page_size=10)
    assert page1.total_rows > 0
    assert len(page1.items) == 10

    filters = repo.get_filter_options(month)
    assert filters["unitup"], "expected at least one UNITUP value"
    filtered = repo.get_customers(month, {"unitup": filters["unitup"][0]}, page=1, page_size=1000)
    assert all(row["UNITUP"] == filters["unitup"][0] for row in filtered.items)


def test_suspect_summary_grand_total_matches_categories():
    repo = DuckDbSuspectRepository()
    month = _first_available_month(repo.get_available_months())
    rows = repo.get_summary(month, {})
    assert rows
    from app.core.suspect_categories import SUSPECT_CATEGORIES
    row = rows[0]
    assert row["GRAND_TOTAL"] == sum(row[c] for c in SUSPECT_CATEGORIES)


def test_suspect_detail_trend_returns_series():
    repo = DuckDbSuspectRepository()
    month = _first_available_month(repo.get_available_months())
    main_page = DuckDbSuspectRepository().get_main(month, page=1, page_size=1, search=None)
    summary_rows = repo.get_summary(month, {})
    location_code = summary_rows[0]["LOCATION_CODE"]
    trend = repo.get_detail_trend(month, location_code)
    assert trend["location_code"] == location_code


ALL_TESTS = [
    test_executive_kpis_roundtrip,
    test_dlpd_customers_pagination_and_filters,
    test_suspect_summary_grand_total_matches_categories,
    test_suspect_detail_trend_returns_series,
]


def main() -> int:
    settings = get_settings()
    print(f"DATA_PROCESSED_DIR = {settings.DATA_PROCESSED_DIR}")
    failures = 0
    for test in ALL_TESTS:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - report, don't crash the whole suite
            failures += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(ALL_TESTS) - failures}/{len(ALL_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
