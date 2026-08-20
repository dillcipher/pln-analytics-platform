from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from app.core.constants import (
    PARQUET,
    WAREHOUSE,
)

logger = logging.getLogger(__name__)


class Warehouse:
    """
    DuckDB Warehouse.

    Responsible for:
    - Opening database connections
    - Refreshing warehouse from parquet files
    - Executing SQL queries
    - Warehouse utilities
    """

    # ==========================================================
    # CONNECTION
    # ==========================================================

    @classmethod
    def connect(
        cls,
    ) -> duckdb.DuckDBPyConnection:

        WAREHOUSE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "Opening DuckDB warehouse: %s",
            WAREHOUSE,
        )

        return duckdb.connect(
            str(WAREHOUSE),
        )

    # ==========================================================
    # REFRESH TABLES
    # ==========================================================

    @classmethod
    def refresh_tables(
        cls,
    ) -> None:

        connection = cls.connect()

        datasets = {

            # --------------------------------------------------
            # ANEV
            # --------------------------------------------------

            "fact_anev":
                PARQUET
                / "anev"
                / "*.parquet",

            # --------------------------------------------------
            # DLPD PASCABAYAR
            # --------------------------------------------------

            "fact_dlpd_pascabayar":
                PARQUET
                / "dlpd"
                / "dlpd_pascabayar*.parquet",

            # --------------------------------------------------
            # DLPD PRABAYAR
            # --------------------------------------------------

            "fact_dlpd_prabayar":
                PARQUET
                / "dlpd"
                / "dlpd_prabayar*.parquet",

            # --------------------------------------------------
            # PENGECEKAN
            # --------------------------------------------------

            "fact_pengecekan":
                PARQUET
                / "pengecekan"
                / "*.parquet",

            # --------------------------------------------------
            # CUSTOMER LOCATION
            #
            # Berisi:
            # IDPEL
            # UNITUPI
            # UNITAP
            # UNITUP
            # KOORDINAT_X
            # KOORDINAT_Y
            # DATASET
            # MONTH
            # --------------------------------------------------

            "fact_customer_location":
                PARQUET
                / "customer_location"
                / "*.parquet",
        }

        try:

            for table_name, parquet_pattern in datasets.items():

                logger.info(
                    "=" * 80,
                )

                logger.info(
                    "Refreshing table : %s",
                    table_name,
                )

                logger.info(
                    "Source : %s",
                    parquet_pattern,
                )

                files = sorted(
                    Path(
                        parquet_pattern.parent,
                    ).glob(
                        parquet_pattern.name,
                    )
                )

                if not files:

                    logger.warning(
                        "No parquet found for %s",
                        table_name,
                    )

                    continue

                connection.execute(
                    f"""
                    CREATE OR REPLACE TABLE {table_name}
                    AS
                    SELECT *
                    FROM read_parquet(
                        '{parquet_pattern.as_posix()}'
                    )
                    """
                )

                connection.execute(
                    f"""
                    ANALYZE {table_name}
                    """
                )

                rows = connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {table_name}
                    """
                ).fetchone()[0]

                logger.info(
                    "%s refreshed (%s rows)",
                    table_name,
                    rows,
                )

            connection.execute(
                """
                CHECKPOINT
                """
            )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "WAREHOUSE REFRESH COMPLETED",
            )

            logger.info(
                "=" * 80,
            )

        finally:

            connection.close()

    # ==========================================================
    # EXECUTE
    # ==========================================================

    @classmethod
    def execute(
        cls,
        query: str,
    ) -> list[tuple]:

        connection = cls.connect()

        try:

            return connection.execute(
                query,
            ).fetchall()

        finally:

            connection.close()

    # ==========================================================
    # LIST TABLES
    # ==========================================================

    @classmethod
    def list_tables(
        cls,
    ) -> list[str]:

        connection = cls.connect()

        try:

            rows = connection.execute(
                """
                SHOW TABLES
                """
            ).fetchall()

            return [
                row[0]
                for row in rows
            ]

        finally:

            connection.close()

    # ==========================================================
    # TABLE EXISTS
    # ==========================================================

    @classmethod
    def table_exists(
        cls,
        table_name: str,
    ) -> bool:

        return (
            table_name
            in cls.list_tables()
        )

    # ==========================================================
    # ROW COUNT
    # ==========================================================

    @classmethod
    def row_count(
        cls,
        table_name: str,
    ) -> int:

        connection = cls.connect()

        try:

            return connection.execute(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                """
            ).fetchone()[0]

        finally:

            connection.close()