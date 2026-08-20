from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


class DuckDBExporter:
    """
    Export processed parquet files
    into a DuckDB database.

    This database is later used
    by dashboard APIs.
    """

    DATABASE_NAME = "analytics.duckdb"

    @classmethod
    def export(
        cls,
        parquet_file: Path,
        table_name: str,
        output_dir: Path,
    ) -> Path:

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        database = output_dir / cls.DATABASE_NAME

        logger.info(
            "Exporting %s -> %s",
            parquet_file.name,
            table_name,
        )

        connection = duckdb.connect(
            str(database)
        )

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name}
            AS
            SELECT *
            FROM read_parquet('{parquet_file}')
            """
        )

        connection.close()

        logger.info(
            "DuckDB updated : %s",
            database,
        )

        return database