from __future__ import annotations

import logging

from app.database.warehouse import Warehouse

logger = logging.getLogger(__name__)


class DashboardRepository:
    """
    Dashboard repository.

    Responsible for querying the DuckDB warehouse.
    """

    @staticmethod
    def execute_one(
        query: str,
    ):

        connection = Warehouse.connect()

        try:

            logger.debug(
                "Executing dashboard query (single row)."
            )

            return connection.execute(
                query
            ).fetchone()

        finally:

            connection.close()

    @staticmethod
    def execute_all(
        query: str,
    ):

        connection = Warehouse.connect()

        try:

            logger.debug(
                "Executing dashboard query (multiple rows)."
            )

            return connection.execute(
                query
            ).fetchall()

        finally:

            connection.close()

    @classmethod
    def get_summary(cls):

        return cls.execute_one(
            """
            SELECT

                COUNT(*) AS total_rows,

                COUNT(DISTINCT LOCATIONCODE) AS total_location,

                COUNT(DISTINCT unitup) AS total_ulp

            FROM fact_anev
            """
        )

    @classmethod
    def get_kpi(cls):

        return cls.execute_one(
            """
            SELECT

                COUNT(*) AS total_customer,

                COUNT(DISTINCT SUSPECTNAME) AS suspect_customer

            FROM fact_anev
            """
        )

    @classmethod
    def get_top_unit(
        cls,
        limit: int = 10,
    ):

        return cls.execute_all(
            f"""
            SELECT

                unitup,

                COUNT(*) AS total_customer,

                COUNT(DISTINCT SUSPECTNAME) AS total_suspect

            FROM fact_anev

            GROUP BY unitup

            ORDER BY total_customer DESC

            LIMIT {limit}
            """
        )

    @classmethod
    def get_location_distribution(
        cls,
    ):

        return cls.execute_all(
            """
            SELECT

                LOCATIONNAME,

                COUNT(*) AS total_customer

            FROM fact_anev

            GROUP BY LOCATIONNAME

            ORDER BY total_customer DESC
            """
        )