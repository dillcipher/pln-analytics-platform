from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from app.core.constants import (
    PARQUET,
    WAREHOUSE,
)
from app.infrastructure.storage.processed_storage import persist_processed_data

logger = logging.getLogger(__name__)


class Warehouse:
    """
    DuckDB Warehouse.

    The processed parquet files are the source of truth. The warehouse
    therefore exposes them as DuckDB views instead of copying every row into
    a second in-process table. This is critical on the production 500 MB
    memory tier: CREATE TABLE AS over a large DLPD dataset can temporarily
    materialize hundreds of MB and trigger an OOM restart.
    """

    _DUCKDB_MEMORY_LIMIT = "192MB"
    _DUCKDB_THREADS = 1

    @classmethod
    def connect(cls) -> duckdb.DuckDBPyConnection:
        WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = WAREHOUSE.parent / "duckdb_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Opening DuckDB warehouse: %s", WAREHOUSE)
        connection = duckdb.connect(str(WAREHOUSE))

        # Keep DuckDB inside the small container's memory budget. Expensive
        # query operators may spill to the local ephemeral disk instead of
        # consuming the whole process memory allowance.
        connection.execute(
            f"SET memory_limit = '{cls._DUCKDB_MEMORY_LIMIT}'"
        )
        connection.execute(
            f"SET threads = {cls._DUCKDB_THREADS}"
        )
        connection.execute("SET preserve_insertion_order = false")
        connection.execute(
            "SET temp_directory = ?",
            [str(temp_dir)],
        )

        return connection

    @classmethod
    def refresh_tables(cls) -> None:
        connection = cls.connect()

        datasets = {
            "fact_anev": PARQUET / "anev" / "*.parquet",
            "fact_dlpd_pascabayar": PARQUET / "dlpd" / "dlpd_pascabayar*.parquet",
            "fact_dlpd_prabayar": PARQUET / "dlpd" / "dlpd_prabayar*.parquet",
            "fact_pengecekan": PARQUET / "pengecekan" / "*.parquet",
            "fact_customer_location": PARQUET / "customer_location" / "*.parquet",
        }

        try:
            for table_name, parquet_pattern in datasets.items():
                logger.info("=" * 80)
                logger.info("Refreshing warehouse view : %s", table_name)
                logger.info("Source : %s", parquet_pattern)

                files = sorted(
                    Path(parquet_pattern.parent).glob(parquet_pattern.name)
                )

                if not files:
                    logger.warning("No parquet found for %s", table_name)
                    continue

                # Never materialize the full parquet dataset into DuckDB.
                # The view is lazy and DuckDB scans only the columns/rows a
                # dashboard query actually needs.
                connection.execute(
                    f"""
                    CREATE OR REPLACE VIEW {table_name}
                    AS
                    SELECT *
                    FROM read_parquet('{parquet_pattern.as_posix()}')
                    """
                )

                rows = connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]

                logger.info(
                    "%s view ready (%s rows)",
                    table_name,
                    rows,
                )

            connection.execute("CHECKPOINT")
            logger.info("=")
            logger.info("WAREHOUSE REFRESH COMPLETED (LAZY PARQUET VIEWS)")
            logger.info("=")
        finally:
            connection.close()

        # Processed data is ephemeral on the cloud instance. Persist it only
        # after the warehouse refresh has completed successfully so finished
        # ETL jobs survive container restarts/redeployments.
        try:
            persisted = persist_processed_data()
            logger.info(
                "Processed artifacts persisted after warehouse refresh: %s file(s).",
                persisted,
            )
        except Exception:
            logger.exception(
                "CRITICAL: warehouse refreshed but processed artifact persistence failed."
            )
            raise

    @classmethod
    def execute(cls, query: str) -> list[tuple]:
        connection = cls.connect()
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    @classmethod
    def list_tables(cls) -> list[str]:
        connection = cls.connect()
        try:
            rows = connection.execute("SHOW TABLES").fetchall()
            return [row[0] for row in rows]
        finally:
            connection.close()

    @classmethod
    def table_exists(cls, table_name: str) -> bool:
        return table_name in cls.list_tables()

    @classmethod
    def row_count(cls, table_name: str) -> int:
        connection = cls.connect()
        try:
            return connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
        finally:
            connection.close()
