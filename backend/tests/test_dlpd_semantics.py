from app.domain.repositories import DlpdFilters
from app.infrastructure.duckdb.dlpd_repository import DuckDbDlpdRepository


def test_all_months_does_not_add_month_predicate():
    repo = DuckDbDlpdRepository.__new__(DuckDbDlpdRepository)
    sql, params = repo._build_where("pascabayar", None, DlpdFilters())
    assert sql == ""
    assert params == []


def test_all_months_repeat_uses_all_available_periods():
    repo = DuckDbDlpdRepository.__new__(DuckDbDlpdRepository)
    sql, params = repo._build_where(
        "pascabayar",
        None,
        DlpdFilters(dlpd_repeat="3"),
    )
    assert "rr.MONTH IS NOT NULL" in sql
    assert "rr.MONTH" in sql
    assert params == [3]


def test_concrete_month_repeat_uses_six_month_window():
    repo = DuckDbDlpdRepository.__new__(DuckDbDlpdRepository)
    sql, params = repo._build_where(
        "pascabayar",
        "202606",
        DlpdFilters(dlpd_repeat="4"),
    )
    assert "IN (?, ?, ?, ?, ?, ?)" in sql
    assert params[0] == "202606"
    assert params[-1] == 4
    assert params[1:7] == [
        "202601",
        "202602",
        "202603",
        "202604",
        "202605",
        "202606",
    ]


def test_month_normalization_accepts_ui_sentinels():
    assert repo_month("__ALL_MONTHS__") is None
    assert repo_month("semua bulan") is None
    assert repo_month("2026-06") == "202606"
    assert repo_month("2026/06") == "202606"


def repo_month(value: str | None) -> str | None:
    from app.infrastructure.duckdb.dlpd_repository import _normalize_month_key

    return _normalize_month_key(value)
