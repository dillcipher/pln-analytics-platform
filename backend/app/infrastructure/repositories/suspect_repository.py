from __future__ import annotations

import logging

from app.database.warehouse import Warehouse

logger = logging.getLogger(__name__)


class SuspectRepository:
    """
    Repository untuk data Suspect / ANEV.

    Sumber utama:
        fact_anev

    Business rule:
        - MONTH berasal langsung dari fact_anev.
        - Tidak ada hardcode periode.
        - LOCATIONCODE dihitung DISTINCT ketika merepresentasikan
          customer/location.
        - Analisis dapat menggunakan satu bulan atau seluruh periode.
    """

    # ==========================================================
    # DATABASE
    # ==========================================================

    @staticmethod
    def execute(
        query: str,
        params: list | tuple | None = None,
    ):
        conn = Warehouse.connect()

        try:
            if params:
                return conn.execute(
                    query,
                    params,
                ).fetchall()

            return conn.execute(query).fetchall()

        finally:
            conn.close()

    # ==========================================================
    # MONTHS
    # ==========================================================

    @classmethod
    def get_months(cls):
        """
        Mengambil seluruh periode yang benar-benar tersedia
        di fact_anev.

        Tidak menggunakan hardcode Januari-Juni.

        Contoh hasil:
            202601
            202602
            202603
            ...
        """

        return cls.execute(
            """
            SELECT DISTINCT
                CAST(MONTH AS VARCHAR) AS MONTH_KEY
            FROM fact_anev
            WHERE
                MONTH IS NOT NULL
            ORDER BY
                MONTH_KEY ASC
            """
        )

    # ==========================================================
    # MAIN
    # ==========================================================

    @classmethod
    def get_main(
        cls,
        month: str | None = None,
    ):
        """
        Summary suspect berdasarkan klasifikasi.

        Jika month diberikan:
            hanya bulan tersebut.

        Jika month None / kosong:
            seluruh periode.
        """

        if month:
            return cls.execute(
                """
                SELECT
                    CAST(SUSPECTNAME AS VARCHAR) AS SUSPECTNAME,

                    COUNT(
                        DISTINCT CAST(
                            LOCATIONCODE AS VARCHAR
                        )
                    ) AS PELANGGAN,

                    COUNT(*) AS FREKUENSI

                FROM fact_anev

                WHERE
                    CAST(MONTH AS VARCHAR) = ?

                GROUP BY
                    SUSPECTNAME

                ORDER BY
                    FREKUENSI DESC
                """,
                [month],
            )

        return cls.execute(
            """
            SELECT
                CAST(SUSPECTNAME AS VARCHAR) AS SUSPECTNAME,

                COUNT(
                    DISTINCT CAST(
                        LOCATIONCODE AS VARCHAR
                    )
                ) AS PELANGGAN,

                COUNT(*) AS FREKUENSI

            FROM fact_anev

            GROUP BY
                SUSPECTNAME

            ORDER BY
                FREKUENSI DESC
            """
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    @classmethod
    def get_summary(
        cls,
        month: str | None = None,
    ):
        """
        Mengambil summary lokasi suspect.

        LOCATIONCODE digunakan sebagai identitas lokasi/customer,
        sehingga jumlah customer tidak dihitung menggunakan
        COUNT(*) secara langsung.
        """

        if month:
            return cls.execute(
                """
                SELECT

                    LOCATIONCODE,

                    LOCATIONNAME,

                    UNITUPI,

                    UNITAP,

                    UNITUP,

                    TARIFF,

                    POWER,

                    COUNT(*) AS GRAND_TOTAL

                FROM fact_anev

                WHERE
                    CAST(MONTH AS VARCHAR) = ?

                GROUP BY

                    LOCATIONCODE,

                    LOCATIONNAME,

                    UNITUPI,

                    UNITAP,

                    UNITUP,

                    TARIFF,

                    POWER

                ORDER BY
                    GRAND_TOTAL DESC
                """,
                [month],
            )

        return cls.execute(
            """
            SELECT

                LOCATIONCODE,

                LOCATIONNAME,

                UNITUPI,

                UNITAP,

                UNITUP,

                TARIFF,

                POWER,

                COUNT(*) AS GRAND_TOTAL

            FROM fact_anev

            GROUP BY

                LOCATIONCODE,

                LOCATIONNAME,

                UNITUPI,

                UNITAP,

                UNITUP,

                TARIFF,

                POWER

            ORDER BY
                GRAND_TOTAL DESC
            """
        )

    # ==========================================================
    # TOTAL LOCATION
    # ==========================================================

    @classmethod
    def get_total_locations(
        cls,
        month: str | None = None,
    ):

        if month:
            rows = cls.execute(
                """
                SELECT
                    COUNT(
                        DISTINCT CAST(
                            LOCATIONCODE AS VARCHAR
                        )
                    )
                FROM fact_anev
                WHERE
                    CAST(MONTH AS VARCHAR) = ?
                    AND LOCATIONCODE IS NOT NULL
                """,
                [month],
            )
        else:
            rows = cls.execute(
                """
                SELECT
                    COUNT(
                        DISTINCT CAST(
                            LOCATIONCODE AS VARCHAR
                        )
                    )
                FROM fact_anev
                WHERE
                    LOCATIONCODE IS NOT NULL
                """
            )

        return int(
            rows[0][0]
            if rows and rows[0][0] is not None
            else 0
        )

    # ==========================================================
    # CLASSIFICATION
    # ==========================================================

    @classmethod
    def get_classification(
        cls,
        month: str | None = None,
    ):

        if month:
            return cls.execute(
                """
                SELECT

                    CAST(
                        SUSPECTNAME AS VARCHAR
                    ) AS CLASSIFICATION,

                    COUNT(
                        DISTINCT CAST(
                            LOCATIONCODE AS VARCHAR
                        )
                    ) AS TOTAL

                FROM fact_anev

                WHERE
                    CAST(MONTH AS VARCHAR) = ?
                    AND SUSPECTNAME IS NOT NULL
                    AND LOCATIONCODE IS NOT NULL

                GROUP BY
                    SUSPECTNAME

                ORDER BY
                    TOTAL DESC
                """,
                [month],
            )

        return cls.execute(
            """
            SELECT

                CAST(
                    SUSPECTNAME AS VARCHAR
                ) AS CLASSIFICATION,

                COUNT(
                    DISTINCT CAST(
                        LOCATIONCODE AS VARCHAR
                    )
                ) AS TOTAL

            FROM fact_anev

            WHERE
                SUSPECTNAME IS NOT NULL
                AND LOCATIONCODE IS NOT NULL

            GROUP BY
                SUSPECTNAME

            ORDER BY
                TOTAL DESC
            """
        )

    # ==========================================================
    # UNITAP
    # ==========================================================

    @classmethod
    def get_unitap(
        cls,
        month: str | None = None,
    ):

        if month:
            return cls.execute(
                """
                SELECT

                    CAST(
                        UNITAP AS VARCHAR
                    ) AS UNITAP,

                    COUNT(
                        DISTINCT CAST(
                            LOCATIONCODE AS VARCHAR
                        )
                    ) AS TOTAL

                FROM fact_anev

                WHERE
                    CAST(MONTH AS VARCHAR) = ?
                    AND UNITAP IS NOT NULL
                    AND LOCATIONCODE IS NOT NULL

                GROUP BY
                    UNITAP

                ORDER BY
                    TOTAL DESC
                """,
                [month],
            )

        return cls.execute(
            """
            SELECT

                CAST(
                    UNITAP AS VARCHAR
                ) AS UNITAP,

                COUNT(
                    DISTINCT CAST(
                        LOCATIONCODE AS VARCHAR
                    )
                ) AS TOTAL

            FROM fact_anev

            WHERE
                UNITAP IS NOT NULL
                AND LOCATIONCODE IS NOT NULL

            GROUP BY
                UNITAP

            ORDER BY
                TOTAL DESC
            """
        )

    # ==========================================================
    # TARIFF
    # ==========================================================

    @classmethod
    def get_tariff(
        cls,
        month: str | None = None,
    ):

        if month:
            return cls.execute(
                """
                SELECT

                    CAST(
                        TARIFF AS VARCHAR
                    ) AS TARIFF,

                    COUNT(
                        DISTINCT CAST(
                            LOCATIONCODE AS VARCHAR
                        )
                    ) AS TOTAL

                FROM fact_anev

                WHERE
                    CAST(MONTH AS VARCHAR) = ?
                    AND TARIFF IS NOT NULL
                    AND LOCATIONCODE IS NOT NULL

                GROUP BY
                    TARIFF

                ORDER BY
                    TOTAL DESC
                """,
                [month],
            )

        return cls.execute(
            """
            SELECT

                CAST(
                    TARIFF AS VARCHAR
                ) AS TARIFF,

                COUNT(
                    DISTINCT CAST(
                        LOCATIONCODE AS VARCHAR
                    )
                ) AS TOTAL

            FROM fact_anev

            WHERE
                TARIFF IS NOT NULL
                AND LOCATIONCODE IS NOT NULL

            GROUP BY
                TARIFF

            ORDER BY
                TOTAL DESC
            """
        )

    # ==========================================================
    # MONTHLY TREND
    # ==========================================================

    @classmethod
    def get_monthly_trend(cls):

        return cls.execute(
            """
            SELECT

                CAST(
                    MONTH AS VARCHAR
                ) AS MONTH_KEY,

                COUNT(
                    DISTINCT CAST(
                        LOCATIONCODE AS VARCHAR
                    )
                ) AS TOTAL

            FROM fact_anev

            WHERE
                MONTH IS NOT NULL
                AND LOCATIONCODE IS NOT NULL

            GROUP BY
                MONTH

            ORDER BY
                MONTH_KEY ASC
            """
        )

    # ==========================================================
    # REPEAT FREQUENCY
    # ==========================================================

    @classmethod
    def get_repeat_frequency(
        cls,
        until_month: str | None = None,
    ):
        """
        Menghitung berapa kali sebuah LOCATIONCODE muncul
        pada bulan yang berbeda.

        Satu occurrence:
            LOCATIONCODE + MONTH

        Jadi banyak row measurement dalam bulan yang sama
        tetap dihitung satu kali.
        """

        if until_month:

            return cls.execute(
                """
                WITH LOCATION_MONTH AS (

                    SELECT DISTINCT

                        CAST(
                            LOCATIONCODE AS VARCHAR
                        ) AS LOCATIONCODE,

                        CAST(
                            MONTH AS VARCHAR
                        ) AS MONTH_KEY

                    FROM fact_anev

                    WHERE
                        LOCATIONCODE IS NOT NULL
                        AND MONTH IS NOT NULL
                        AND CAST(MONTH AS VARCHAR) <= ?

                ),

                FREQUENCY AS (

                    SELECT

                        LOCATIONCODE,

                        COUNT(*) AS REPEAT_COUNT

                    FROM LOCATION_MONTH

                    GROUP BY
                        LOCATIONCODE

                )

                SELECT

                    REPEAT_COUNT,

                    COUNT(*) AS LOCATIONS

                FROM FREQUENCY

                GROUP BY
                    REPEAT_COUNT

                ORDER BY
                    REPEAT_COUNT ASC
                """,
                [until_month],
            )

        return cls.execute(
            """
            WITH LOCATION_MONTH AS (

                SELECT DISTINCT

                    CAST(
                        LOCATIONCODE AS VARCHAR
                    ) AS LOCATIONCODE,

                    CAST(
                        MONTH AS VARCHAR
                    ) AS MONTH_KEY

                FROM fact_anev

                WHERE
                    LOCATIONCODE IS NOT NULL
                    AND MONTH IS NOT NULL

            ),

            FREQUENCY AS (

                SELECT

                    LOCATIONCODE,

                    COUNT(*) AS REPEAT_COUNT

                FROM LOCATION_MONTH

                GROUP BY
                    LOCATIONCODE

            )

            SELECT

                REPEAT_COUNT,

                COUNT(*) AS LOCATIONS

            FROM FREQUENCY

            GROUP BY
                REPEAT_COUNT

            ORDER BY
                REPEAT_COUNT ASC
            """
        )

    # ==========================================================
    # REPEAT SUMMARY
    # ==========================================================

    @classmethod
    def get_repeat_summary(
        cls,
        until_month: str | None = None,
    ):

        if until_month:

            rows = cls.execute(
                """
                WITH LOCATION_MONTH AS (

                    SELECT DISTINCT

                        CAST(
                            LOCATIONCODE AS VARCHAR
                        ) AS LOCATIONCODE,

                        CAST(
                            MONTH AS VARCHAR
                        ) AS MONTH_KEY

                    FROM fact_anev

                    WHERE
                        LOCATIONCODE IS NOT NULL
                        AND MONTH IS NOT NULL
                        AND CAST(MONTH AS VARCHAR) <= ?

                ),

                FREQUENCY AS (

                    SELECT

                        LOCATIONCODE,

                        COUNT(*) AS MONTHS_SEEN

                    FROM LOCATION_MONTH

                    GROUP BY
                        LOCATIONCODE

                )

                SELECT

                    COUNT(*) AS TOTAL_CUSTOMERS,

                    COUNT(
                        CASE
                            WHEN MONTHS_SEEN > 1
                            THEN 1
                        END
                    ) AS REPEAT_CUSTOMERS,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN MONTHS_SEEN > 1
                                THEN MONTHS_SEEN - 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS REPEAT_OCCURRENCES

                FROM FREQUENCY
                """,
                [until_month],
            )

        else:

            rows = cls.execute(
                """
                WITH LOCATION_MONTH AS (

                    SELECT DISTINCT

                        CAST(
                            LOCATIONCODE AS VARCHAR
                        ) AS LOCATIONCODE,

                        CAST(
                            MONTH AS VARCHAR
                        ) AS MONTH_KEY

                    FROM fact_anev

                    WHERE
                        LOCATIONCODE IS NOT NULL
                        AND MONTH IS NOT NULL

                ),

                FREQUENCY AS (

                    SELECT

                        LOCATIONCODE,

                        COUNT(*) AS MONTHS_SEEN

                    FROM LOCATION_MONTH

                    GROUP BY
                        LOCATIONCODE

                )

                SELECT

                    COUNT(*) AS TOTAL_CUSTOMERS,

                    COUNT(
                        CASE
                            WHEN MONTHS_SEEN > 1
                            THEN 1
                        END
                    ) AS REPEAT_CUSTOMERS,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN MONTHS_SEEN > 1
                                THEN MONTHS_SEEN - 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS REPEAT_OCCURRENCES

                FROM FREQUENCY
                """
            )

        if not rows:
            return {
                "total_customers": 0,
                "repeat_customers": 0,
                "repeat_occurrences": 0,
                "repeat_rate_pct": 0.0,
            }

        row = rows[0]

        total_customers = int(
            row[0] or 0
        )

        repeat_customers = int(
            row[1] or 0
        )

        repeat_occurrences = int(
            row[2] or 0
        )

        repeat_rate_pct = (
            round(
                repeat_customers
                / total_customers
                * 100,
                2,
            )
            if total_customers
            else 0.0
        )

        return {
            "total_customers": total_customers,
            "repeat_customers": repeat_customers,
            "repeat_occurrences": repeat_occurrences,
            "repeat_rate_pct": repeat_rate_pct,
        }