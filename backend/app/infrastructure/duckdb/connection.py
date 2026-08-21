from __future__ import annotations

import logging
import threading
from pathlib import Path

import duckdb

from app.core.constants import WAREHOUSE, PARQUET

logger = logging.getLogger(__name__)


_thread_state = threading.local()


def _get_thread_connection() -> duckdb.DuckDBPyConnection | None:
    return getattr(_thread_state, "connection", None)


def _set_thread_connection(
    conn: duckdb.DuckDBPyConnection | None,
) -> None:
    _thread_state.connection = conn


def _is_connection_alive(
    conn: duckdb.DuckDBPyConnection | None,
) -> bool:
    if conn is None:
        return False

    try:
        conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def _open_connection() -> duckdb.DuckDBPyConnection:
    Path(WAREHOUSE).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info("Opening DuckDB read connection: %s", WAREHOUSE)

    try:
        return duckdb.connect(
            str(WAREHOUSE),
            read_only=True,
        )
    except Exception:
        return duckdb.connect(str(WAREHOUSE))


def _has_registered_fact_tables(
    conn: duckdb.DuckDBPyConnection,
) -> bool:
    """Return whether the warehouse has at least one application fact table."""
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name IN (
                'fact_anev',
                'fact_dlpd_prabayar',
                'fact_dlpd_pascabayar',
                'fact_pengecekan',
                'fact_customer_location'
            )
            """
        ).fetchone()
        return bool(row and row[0])
    except Exception:
        return False


def _processed_parquet_exists() -> bool:
    """Check whether durable processed parquet exists before rebuilding."""
    try:
        if not PARQUET.exists():
            return False
        return any(PARQUET.rglob("*.parquet"))
    except Exception:
        return False


def _ensure_warehouse_tables(
    conn: duckdb.DuckDBPyConnection,
) -> duckdb.DuckDBPyConnection:
    """Self-heal a fresh cloud instance whose DuckDB tables are missing.

    FastAPI Cloud instances are disposable. Processed parquet files are
    durable, while the local DuckDB catalog can be absent/stale. If an API
    worker opens such a warehouse before startup hydration/refresh has taken
    effect, rebuild the catalog once and reopen the read connection.
    """
    if _has_registered_fact_tables(conn):
        return conn

    if not _processed_parquet_exists():
        return conn

    logger.warning(
        "Warehouse has no registered fact tables although processed parquet "
        "exists; rebuilding DuckDB catalog before serving the request."
    )

    try:
        conn.close()
    except Exception:
        pass

    try:
        # Import lazily to avoid an import cycle during application startup.
        from app.database.warehouse import Warehouse

        Warehouse.refresh_tables()
        logger.info("On-demand warehouse refresh completed.")
        return _open_connection()
    except Exception:
        logger.exception("On-demand warehouse refresh failed.")
        return _open_connection()


def get_connection() -> duckdb.DuckDBPyConnection:
    conn = _get_thread_connection()

    if _is_connection_alive(conn):
        return conn  # type: ignore[return-value]

    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    conn = _open_connection()
    conn = _ensure_warehouse_tables(conn)
    _set_thread_connection(conn)
    return conn


def close_connection() -> None:
    conn = _get_thread_connection()

    if conn is None:
        return

    try:
        conn.close()
    except Exception:
        pass
    finally:
        _set_thread_connection(None)


def dataset_exists(dataset_name: str) -> bool:
    conn = get_connection()

    try:
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [dataset_name],
        ).fetchone()
        return bool(result and result[0])
    except Exception:
        return False


def table_exists(table_name: str) -> bool:
    return dataset_exists(table_name)


def list_tables() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SHOW TABLES").fetchall()
    return [str(row[0]) for row in rows]


def row_count(table_name: str) -> int:
    conn = get_connection()
    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(result[0]) if result else 0


def list_month_partitions(dataset_name: str) -> list[str]:
    if not dataset_exists(dataset_name):
        return []

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT MONTH_KEY
            FROM {dataset_name}
            WHERE MONTH_KEY IS NOT NULL
            ORDER BY MONTH_KEY
            """
        ).fetchall()
        return [str(row[0]) for row in rows]
    except Exception:
        return []


def read_dataset_sql(
    dataset_name: str,
    month_key: str | None = None,
) -> str:
    if not dataset_exists(dataset_name):
        raise ValueError(
            f"Dataset '{dataset_name}' does not exist."
        )

    return dataset_name
