"""Runtime guard for memory-heavy DLPD read queries.

The DLPD page intentionally requests several read endpoints at the same time:
KPI, ULP, customer list and map.  Each endpoint opens DuckDB and can execute a
large parquet scan.  On the 500 MB service tier, concurrent scans can exceed
the container limit even though each individual query is valid.

This module serializes those heavy DLPD reads per application instance.  It
is deliberately small and does not change query semantics or API contracts.
"""

from __future__ import annotations

import gc
import logging
import threading
import time
from functools import wraps
from typing import Any, Callable

from app.infrastructure.duckdb.dlpd_repository import DuckDbDlpdRepository

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_INSTALLED = False

_METHODS = (
    "get_available_months",
    "get_filter_options",
    "get_dashboard",
    "get_dashboard_ulp",
    "get_customers",
    "get_customer_detail",
    "export_customers",
    "get_map_points",
)


def install_dlpd_query_guard() -> None:
    """Install the per-process DLPD query memory gate exactly once."""
    global _INSTALLED

    if _INSTALLED:
        return

    for method_name in _METHODS:
        original = getattr(DuckDbDlpdRepository, method_name)

        if getattr(original, "_dlpd_query_guard", False):
            continue

        @wraps(original)
        def guarded(
            self: DuckDbDlpdRepository,
            *args: Any,
            __original: Callable[..., Any] = original,
            __method_name: str = method_name,
            **kwargs: Any,
        ) -> Any:
            wait_started = time.perf_counter()

            with _LOCK:
                waited = time.perf_counter() - wait_started
                if waited >= 0.05:
                    logger.info(
                        "DLPD QUERY QUEUED | method=%s | waited=%.2fs",
                        __method_name,
                        waited,
                    )

                try:
                    return __original(
                        self,
                        *args,
                        **kwargs,
                    )
                finally:
                    # Encourage prompt release of temporary Python objects
                    # after a large parquet query. DuckDB owns its own memory
                    # and is still closed by the repository method where the
                    # implementation explicitly closes its connection.
                    gc.collect()

        guarded._dlpd_query_guard = True  # type: ignore[attr-defined]
        setattr(DuckDbDlpdRepository, method_name, guarded)

    _INSTALLED = True
    logger.info(
        "DLPD query memory guard installed | serialized_methods=%s",
        len(_METHODS),
    )
