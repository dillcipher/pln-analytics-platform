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

    Processed parquet files are the source of truth. The warehouse exposes
    them as lazy DuckDB views instead of copying the full datasets into a
    second in-memory table. This is required for the production 500 MB
    memory tier, especially for the large Pascabayar workbook.
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

        # Keep DuckDB from consuming the entire container. Expensive query
        # operators can spill to local ephemeral disk instead.
        connection.execute(
            f"SET memory_limit = '{cls._DUCKDB_MEMORY_LIMIT}'"
        )
        connection.execute(f"SET threads = {cls._DUCKDB_THREADS}")
        connection.execute("SET preserve_insertion_order = false")
        connection.execute("SET temp_directory = ?", [str(temp_dir)])

        return connection

    @staticmethod
    def _replace_with_parquet_view(
        connection: duckdb.DuckDBPyConnection,
        view_name: str,
        parquet_pattern: Path,
    ) -> None:
        """Replace an old table/view with a lazy parquet-backed view."""
        relation_type = connection.execute(
            """
            SELECT table_type
            FROM information_schema.tables
            WHERE table_name = ?
            LIMIT 1
            """,
            [view_name],
        ).fetchone()

        if relation_type:
            object_type = str(relation_type[0]).upper()
            if object_type == "VIEW":
                connection.execute(f"DROP VIEW {view_name}")
            else:
                # Handles the old materialized TABLE created by previous
                # releases. Dropping it releases the old warehouse storage
                # without scanning or rebuilding the dataset in memory.
                connection.execute(f"DROP TABLE {view_name}")

        connection.execute(
            f"""
            CREATE VIEW {view_name}
            AS
            SELECT *
            FROM read_parquet('{parquet_pattern.as_posix()}')
            """
        )

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

                # No COUNT(*) here. A count would force a full scan during
                # every refresh and gives no value to the dashboard runtime.
                cls._replace_with_parquet_view(
                    connection,
                    table_name,
                    parquet_pattern,
                )
                logger.info("%s view ready", table_name)

            connection.execute("CHECKPOINT")
            logger.info("=")
            logger.info("WAREHOUSE REFRESH COMPLETED (LAZY PARQUET VIEWS)")
            logger.info("=")
        finally:
            connection.close()

        # Persist only after the lightweight warehouse refresh succeeds.
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
            rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_name
                """
            ).fetchall()
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
