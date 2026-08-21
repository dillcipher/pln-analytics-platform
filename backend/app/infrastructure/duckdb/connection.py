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


def _table_exists_on_connection(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> bool:
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchone()
        return bool(row and row[0])
    except Exception:
        return False


def _warehouse_needs_refresh(
    conn: duckdb.DuckDBPyConnection,
) -> bool:
    """Detect durable parquet that is not yet registered in DuckDB."""
    datasets = {
        "fact_anev": PARQUET / "anev" / "*.parquet",
        "fact_dlpd_pascabayar": PARQUET / "dlpd" / "dlpd_pascabayar*.parquet",
        "fact_dlpd_prabayar": PARQUET / "dlpd" / "dlpd_prabayar*.parquet",
        "fact_pengecekan": PARQUET / "pengecekan" / "*.parquet",
        "fact_customer_location": PARQUET / "customer_location" / "*.parquet",
    }

    for table_name, pattern in datasets.items():
        try:
            has_parquet = any(pattern.parent.glob(pattern.name))
        except Exception:
            has_parquet = False

        if has_parquet and not _table_exists_on_connection(conn, table_name):
            logger.warning(
                "Durable parquet exists for %s but the DuckDB table is missing.",
                table_name,
            )
            return True

    return False


def _ensure_warehouse_tables(
    conn: duckdb.DuckDBPyConnection,
) -> duckdb.DuckDBPyConnection:
    """Self-heal a cloud instance when durable parquet is not registered."""
    if not _warehouse_needs_refresh(conn):
        return conn

    logger.warning(
        "Warehouse catalog is stale/missing; rebuilding from durable parquet."
    )

    try:
        conn.close()
    except Exception:
        pass

    try:
        # Lazy import avoids the connection -> warehouse -> connection cycle.
        from app.database.warehouse import Warehouse

        Warehouse.refresh_tables()
        logger.info("On-demand warehouse refresh completed.")
    except Exception:
        logger.exception("On-demand warehouse refresh failed.")

    return _open_connection()


def get_connection() -> duckdb.DuckDBPyConnection:
    conn = _get_thread_connection()

    if _is_connection_alive(conn):
        # A worker can stay alive across an ETL run. In that case its
        # read-only connection may have been opened before new parquet was
        # persisted. Re-check the catalog even for an existing connection.
        conn = _ensure_warehouse_tables(conn)  # type: ignore[arg-type]
        _set_thread_connection(conn)
        return conn

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
