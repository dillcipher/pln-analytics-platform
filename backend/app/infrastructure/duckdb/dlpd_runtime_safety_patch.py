"""Runtime safety guards for DLPD dashboard endpoints.

The API is deployed on ephemeral replicas. During a fresh deployment the
processed parquet datasets may legitimately be absent for a short period.
The dashboard should show an empty state instead of turning that condition
into HTTP 503/CatalogException.
"""

from __future__ import annotations

from app.infrastructure.duckdb.connection import dataset_exists
from app.infrastructure.duckdb.dlpd_repository import DuckDbDlpdRepository


_INSTALLED = False
_ORIGINAL_GET_DASHBOARD_ULP = DuckDbDlpdRepository.get_dashboard_ulp


def _safe_get_dashboard_ulp(self, customer_type, month_key, filters):
    table = self._table(customer_type)
    if not dataset_exists(table):
        return []
    return _ORIGINAL_GET_DASHBOARD_ULP(self, customer_type, month_key, filters)


def install_dlpd_runtime_safety_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    DuckDbDlpdRepository.get_dashboard_ulp = _safe_get_dashboard_ulp
    _INSTALLED = True
