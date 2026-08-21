"""
DuckDB-backed implementation of `ExecutiveRepository`.

Executive Dashboard menggunakan processed DuckDB datasets dan fact tables
yang memang tersedia di database.

Sumber utama Executive:

    - executive_kpis
        Existing KPI snapshot, jika tersedia.

    - fact_anev
        Sumber utama seluruh analitik ANEV:
            - klasifikasi suspect
            - UNITAP
            - UNITUP
            - tarif
            - PRA monthly analysis
            - PASCA repeat analysis
            - repeat by classification
            - UNITAP x classification heatmap

Business rules:

    PRA
        Analisis hanya dilakukan pada bulan yang dipilih.

    PASCA
        Repeat dihitung lintas bulan sampai bulan yang dipilih.

        Satu occurrence didefinisikan sebagai:
            LOCATION_CODE + MONTH

        Jadi banyak measurement row untuk LOCATION_CODE yang sama
        dalam bulan yang sama tidak dihitung sebagai banyak repeat.

Important:

    fact_anev adalah measurement-level fact table.

    Oleh karena itu, untuk analisis customer/location digunakan
    DISTINCT LOCATION_CODE.

    Jangan menggunakan COUNT(*) untuk menghitung jumlah customer/location.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.month_utils import month_keys_to_options
from app.domain.entities import KpiSet, MonthOption
from app.infrastructure.duckdb.connection import (
    dataset_exists,
    get_connection,
    list_month_partitions,
    read_dataset_sql,
)

logger = logging.getLogger(__name__)


class DuckDbExecutiveRepository:
    """
    DuckDB implementation of the Executive Dashboard repository.
    """

    # ==========================================================
    # MONTHS
    # ==========================================================

    def get_available_months(
        self,
    ) -> list[MonthOption]:
        """
        Return available Executive Dashboard months.

        Prefer executive_kpis partitions when available.

        If executive_kpis does not exist, fall back to MONTH values
        from fact_anev.
        """

        if dataset_exists("executive_kpis"):
            months = list_month_partitions(
                "executive_kpis",
            )

            if months:
                return month_keys_to_options(
                    months,
                )

        conn = get_connection()

        try:
            rows = conn.execute(
                """
                SELECT DISTINCT
                    CAST(MONTH AS VARCHAR) AS month_key
                FROM fact_anev
                WHERE MONTH IS NOT NULL
                ORDER BY month_key
                """
            ).fetchall()

            months = [
                str(row[0])
                for row in rows
                if row[0] is not None
            ]

            return month_keys_to_options(
                months,
            )

        finally:
            conn.close()

    # ==========================================================
    # KPI
    # ==========================================================

    def get_kpis(
        self,
        month_key: str,
    ) -> KpiSet | None:
        """
        Retrieve Executive KPI snapshot.

        When ``executive_kpis`` is unavailable or does not contain the
        requested month, derive the KPI from the same fact tables used by
        the Executive charts. This prevents the dashboard from displaying
        a misleading all-zero KPI while ANEV data is available.

        Derived definition:
            total_customers = distinct LOCATION_CODE in fact_anev for month
            total_suspects  = distinct LOCATION_CODE in fact_anev for month
            normal          = distinct suspect locations with latest
                              inspection classified as NORMAL
            findings        = inspected locations not classified NORMAL
            remaining       = total_customers - inspected
            progress        = inspected / total_customers * 100
            hit_rate        = findings / total_suspects * 100
        """

        if not month_key:
            return None

        conn = get_connection()

        try:
            if dataset_exists("executive_kpis"):
                try:
                    sql = f"""
                        SELECT
                            MONTH_KEY,
                            TOTAL_CUSTOMERS,
                            TOTAL_SUSPECTS,
                            TOTAL_NORMAL,
                            TOTAL_FINDINGS,
                            REMAINING_INSPECTION,
                            PROGRESS_PCT,
                            HIT_RATE_PCT
                        FROM {read_dataset_sql(
                            "executive_kpis",
                            month_key,
                        )}
                        WHERE MONTH_KEY = ?
                        LIMIT 1
                    """

                    row = conn.execute(
                        sql,
                        [month_key],
                    ).fetchone()

                    if row is not None:
                        return KpiSet(
                            month_key=str(row[0]),
                            total_customers=int(
                                row[1] or 0
                            ),
                            total_suspects=int(
                                row[2] or 0
                            ),
                            total_normal=int(
                                row[3] or 0
                            ),
                            total_findings=int(
                                row[4] or 0
                            ),
                            remaining_inspection=int(
                                row[5] or 0
                            ),
                            progress_pct=float(
                                row[6] or 0
                            ),
                            hit_rate_pct=float(
                                row[7] or 0
                            ),
                        )
                except Exception:
                    logger.exception(
                        "Failed to read executive_kpis; "
                        "falling back to fact tables."
                    )

            # --------------------------------------------------
            # Fact-table fallback
            # --------------------------------------------------

            if not dataset_exists("fact_anev"):
                return None

            # fact_pengecekan is optional. If it is not available yet,
            # KPI derivation must still work and report zero inspected rows.
            if dataset_exists("fact_pengecekan"):
                inspection_cte = """
                latest_inspection AS (
                    SELECT
                        CAST(IDPEL AS VARCHAR) AS IDPEL,
                        STATUS_KWH,
                        UPDATE_STATUS,

                        ROW_NUMBER() OVER (
                            PARTITION BY CAST(IDPEL AS VARCHAR)
                            ORDER BY
                                WAKTU_PERIKSA DESC NULLS LAST
                        ) AS RN

                    FROM fact_pengecekan

                    WHERE IDPEL IS NOT NULL
                )
                """
            else:
                inspection_cte = """
                latest_inspection AS (
                    SELECT
                        CAST(NULL AS VARCHAR) AS IDPEL,
                        CAST(NULL AS VARCHAR) AS STATUS_KWH,
                        CAST(NULL AS VARCHAR) AS UPDATE_STATUS,
                        CAST(NULL AS BIGINT) AS RN
                    WHERE FALSE
                )
                """

            sql = f"""
            WITH suspect_locations AS (
                SELECT DISTINCT
                    CAST(LOCATION_CODE AS VARCHAR) AS IDPEL
                FROM fact_anev
                WHERE
                    CAST(MONTH AS VARCHAR) = ?
                    AND LOCATION_CODE IS NOT NULL
            ),

            {inspection_cte},

            inspected AS (
                SELECT
                    s.IDPEL,
                    p.STATUS_KWH,
                    p.UPDATE_STATUS
                FROM suspect_locations s
                INNER JOIN latest_inspection p
                    ON s.IDPEL = p.IDPEL
                    AND p.RN = 1
            )

            SELECT
                (SELECT COUNT(*) FROM suspect_locations) AS TOTAL_CUSTOMERS,

                (SELECT COUNT(*) FROM suspect_locations) AS TOTAL_SUSPECTS,

                (
                    SELECT COUNT(*)
                    FROM inspected
                    WHERE UPPER(
                        COALESCE(
                            STATUS_KWH,
                            UPDATE_STATUS,
                            ''
                        )
                    ) LIKE '%NORMAL%'
                ) AS TOTAL_NORMAL,

                (
                    SELECT COUNT(*)
                    FROM inspected
                    WHERE UPPER(
                        COALESCE(
                            STATUS_KWH,
                            UPDATE_STATUS,
                            ''
                        )
                    ) NOT LIKE '%NORMAL%'
                ) AS TOTAL_FINDINGS,

                (SELECT COUNT(*) FROM suspect_locations)
                -
                (SELECT COUNT(*) FROM inspected)
                    AS REMAINING_INSPECTION,

                (
                    SELECT COUNT(*)
                    FROM inspected
                ) AS INSPECTED
            """

            row = conn.execute(
                sql,
                [str(month_key)],
            ).fetchone()

            if row is None:
                return None

            total_customers = int(row[0] or 0)
            total_suspects = int(row[1] or 0)
            total_normal = int(row[2] or 0)
            total_findings = int(row[3] or 0)
            remaining = max(
                int(row[4] or 0),
                0,
            )
            inspected_count = int(row[5] or 0)

            progress = (
                inspected_count
                / total_customers
                * 100
                if total_customers > 0
                else 0.0
            )

            hit_rate = (
                total_findings
                / total_suspects
                * 100
                if total_suspects > 0
                else 0.0
            )

            return KpiSet(
                month_key=str(month_key),
                total_customers=total_customers,
                total_suspects=total_suspects,
                total_normal=total_normal,
                total_findings=total_findings,
                remaining_inspection=remaining,
                progress_pct=round(
                    progress,
                    2,
                ),
                hit_rate_pct=round(
                    hit_rate,
                    2,
                ),
            )

        finally:
            conn.close()


    # ==========================================================
    # CHART DATA
    # ==========================================================

    def get_chart_data(
        self,
        month_key: str,
    ) -> dict[str, Any]:
        """
        Return complete Executive Dashboard chart data.

        Semua chart sekarang bersumber dari fact_anev.

        Tidak lagi bergantung pada dataset `dlpd_customer`.

        Output:

            bar_by_unitap
            pie_by_tariff
            donut_by_segment
            monthly_trend
            ranking_by_ulp
            heatmap_unitap_x_category

            anev_classification
            anev_by_unitap
            anev_by_tariff

            pra_monthly
            pasca_repeat
            repeat_cases

            data_science
                - priority_by_classification
                - priority_by_unitap
                - inspection_coverage
                - repeat_intensity
                - concentration
                - PRA vs PASCA classification comparison
        """

        result: dict[str, Any] = {
            # --------------------------------------------------
            # Executive legacy chart keys
            # --------------------------------------------------

            "bar_by_unitap": [],
            "pie_by_tariff": [],
            "donut_by_segment": [],
            "monthly_trend": [],
            "ranking_by_ulp": [],
            "heatmap_unitap_x_category": [],

            # --------------------------------------------------
            # ANEV
            # --------------------------------------------------

            "anev_classification": [],
            "anev_by_unitap": [],
            "anev_by_tariff": [],

            # --------------------------------------------------
            # PRA
            # --------------------------------------------------

            "pra_monthly": {
                "total_locations": 0,
                "total_classifications": 0,
                "classification": [],
                "unitap": [],
            },

            # --------------------------------------------------
            # PASCA
            # --------------------------------------------------

            "pasca_repeat": {
                "total_locations": 0,
                "repeat_locations": 0,
                "repeat_occurrences": 0,
                "repeat_rate_pct": 0.0,
                "frequency": [],
                "classification": [],
            },

            # --------------------------------------------------
            # Compatibility
            # --------------------------------------------------

            "repeat_cases": [],

            # --------------------------------------------------
            # Data Science / Analytical layer
            # --------------------------------------------------

            "data_science": {
                "correlation": [],
                "linear_regression": [],
                "feature_importance": [],
                "pra_pasca_classification": [],
                "priority_by_unitap": [],
                "priority_by_classification": [],
                "inspection_coverage": {},
                "repeat_intensity": {},
                "concentration": {},
            },
        }

        if not month_key:
            logger.warning(
                "Executive chart requested without month_key."
            )
            return result

        conn = get_connection()

        try:
            if not self._fact_anev_exists(conn):
                logger.warning(
                    "Table 'fact_anev' does not exist."
                )
                return result

            # ==================================================
            # ANEV / EXECUTIVE DISTRIBUTION
            # ==================================================

            self._load_anev_charts(
                conn,
                month_key,
                result,
            )

            # ==================================================
            # HISTORICAL TREND
            # ==================================================

            self._load_monthly_trend(
                conn,
                month_key,
                result,
            )

            # ==================================================
            # PRA
            # ==================================================

            self._load_pra(
                conn,
                month_key,
                result,
            )

            # ==================================================
            # PASCA
            # ==================================================

            self._load_pasca_repeat(
                conn,
                month_key,
                result,
            )

            # ==================================================
            # DATA SCIENCE / ANALYTICAL LAYER
            # ==================================================

            self._load_data_science(
                conn,
                month_key,
                result,
            )

            # ==================================================
            # HEATMAP
            # ==================================================

            self._load_heatmap(
                conn,
                month_key,
                result,
            )

            # ==================================================
            # COMPATIBILITY MAPPING
            #
            # Frontend lama tetap mendapatkan key:
            #
            # bar_by_unitap
            # pie_by_tariff
            # ranking_by_ulp
            #
            # tanpa membutuhkan dlpd_customer.
            # ==================================================

            result["bar_by_unitap"] = list(
                result["anev_by_unitap"]
            )

            result["pie_by_tariff"] = list(
                result["anev_by_tariff"]
            )

            return result

        finally:
            conn.close()

    # ==========================================================
    # ANEV CHARTS
    # ==========================================================

    def _load_anev_charts(
        self,
        conn,
        month_key: str,
        result: dict[str, Any],
    ) -> None:
        """
        Build Executive ANEV analytics from fact_anev.

        Semua customer/location dihitung DISTINCT LOCATION_CODE.
        """

        # ======================================================
        # 1. CLASSIFICATION
        #
        # Selected month.
        #
        # Satu LOCATION_CODE dihitung sekali untuk setiap
        # klasifikasi.
        # ======================================================

        classification_sql = """
            SELECT
                CAST(SUSPECT_NAME AS VARCHAR) AS label,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS value

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND SUSPECT_NAME IS NOT NULL

            GROUP BY
                SUSPECT_NAME

            ORDER BY
                value DESC
        """

        classification_rows = conn.execute(
            classification_sql,
            [month_key],
        ).fetchall()

        result["anev_classification"] = [
            {
                "label": row[0],
                "value": int(row[1] or 0),
            }
            for row in classification_rows
        ]

        # ======================================================
        # 2. BY UNITAP
        # ======================================================

        unitap_sql = """
            SELECT
                CAST(UNITAP AS VARCHAR) AS label,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS value

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND UNITAP IS NOT NULL

            GROUP BY
                UNITAP

            ORDER BY
                value DESC
        """

        unitap_rows = conn.execute(
            unitap_sql,
            [month_key],
        ).fetchall()

        result["anev_by_unitap"] = [
            {
                "label": row[0],
                "value": int(row[1] or 0),
            }
            for row in unitap_rows
        ]

        # ======================================================
        # 3. BY TARIF
        # ======================================================

        tariff_sql = """
            SELECT
                CAST(TARIFF AS VARCHAR) AS label,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS value

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND TARIFF IS NOT NULL

            GROUP BY
                TARIFF

            ORDER BY
                value DESC
        """

        tariff_rows = conn.execute(
            tariff_sql,
            [month_key],
        ).fetchall()

        result["anev_by_tariff"] = [
            {
                "label": row[0],
                "value": int(row[1] or 0),
            }
            for row in tariff_rows
        ]

        # ======================================================
        # 4. BY ULP
        #
        # Ranking ULP menggunakan UNITUP.
        # ======================================================

        ulp_sql = """
            SELECT
                CAST(UNITUP AS VARCHAR) AS label,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS value

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND UNITUP IS NOT NULL

            GROUP BY
                UNITUP

            ORDER BY
                value DESC

            LIMIT 10
        """

        ulp_rows = conn.execute(
            ulp_sql,
            [month_key],
        ).fetchall()

        result["ranking_by_ulp"] = [
            {
                "label": row[0],
                "value": int(row[1] or 0),
            }
            for row in ulp_rows
        ]

        # ======================================================
        # 5. SEGMENT
        #
        # fact_anev tidak mempunyai kolom SEGMENT.
        #
        # Jangan mengarang segment dari kolom lain.
        # ======================================================

        result["donut_by_segment"] = []

    # ==========================================================
    # MONTHLY TREND
    # ==========================================================

    def _load_monthly_trend(
        self,
        conn,
        month_key: str,
        result: dict[str, Any],
    ) -> None:
        """
        Historical ANEV location trend.

        Setiap bulan dihitung sebagai DISTINCT LOCATION_CODE.

        Hanya bulan sampai selected month yang ditampilkan.
        """

        trend_sql = """
            SELECT
                CAST(MONTH AS VARCHAR) AS label,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS value

            FROM fact_anev

            WHERE
                MONTH IS NOT NULL
                AND LOCATION_CODE IS NOT NULL
                AND CAST(MONTH AS VARCHAR) <= ?

            GROUP BY
                MONTH

            ORDER BY
                label ASC
        """

        rows = conn.execute(
            trend_sql,
            [month_key],
        ).fetchall()

        result["monthly_trend"] = [
            {
                "label": str(row[0]),
                "value": int(row[1] or 0),
            }
            for row in rows
        ]

    # ==========================================================
    # PRA
    # ==========================================================

    def _load_pra(
        self,
        conn,
        month_key: str,
        result: dict[str, Any],
    ) -> None:
        """
        PRA = analisis per bulan.

        Tidak ada cross-month repetition.

        Untuk bulan yang dipilih:
            LOCATION_CODE dihitung sekali.
        """

        # ======================================================
        # TOTAL LOCATION
        # ======================================================

        total_sql = """
            SELECT
                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                )

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
        """

        total_row = conn.execute(
            total_sql,
            [month_key],
        ).fetchone()

        total_locations = (
            int(total_row[0] or 0)
            if total_row
            else 0
        )

        # ======================================================
        # CLASSIFICATION
        # ======================================================

        classification_sql = """
            SELECT
                CAST(
                    SUSPECT_NAME AS VARCHAR
                ) AS classification,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS total

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND SUSPECT_NAME IS NOT NULL

            GROUP BY
                SUSPECT_NAME

            ORDER BY
                total DESC
        """

        classification_rows = conn.execute(
            classification_sql,
            [month_key],
        ).fetchall()

        classifications = [
            {
                "classification": row[0],
                "total": int(row[1] or 0),
            }
            for row in classification_rows
        ]

        # ======================================================
        # UNITAP
        # ======================================================

        unitap_sql = """
            SELECT
                CAST(
                    UNITAP AS VARCHAR
                ) AS unitap,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS total

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND UNITAP IS NOT NULL

            GROUP BY
                UNITAP

            ORDER BY
                total DESC
        """

        unitap_rows = conn.execute(
            unitap_sql,
            [month_key],
        ).fetchall()

        unitap = [
            {
                "unitap": row[0],
                "total": int(row[1] or 0),
            }
            for row in unitap_rows
        ]

        result["pra_monthly"] = {
            "total_locations": total_locations,
            "total_classifications": len(
                classifications
            ),
            "classification": classifications,
            "unitap": unitap,
        }

    # ==========================================================
    # PASCA REPEAT
    # ==========================================================

    def _load_pasca_repeat(
        self,
        conn,
        month_key: str,
        result: dict[str, Any],
    ) -> None:
        """
        PASCA = repeat analysis lintas bulan.

        Business rule:

            LOCATION_CODE + MONTH = 1 occurrence.

        Contoh:

            Jan + Feb + Mar
                -> repeat_count = 3

        Banyak measurement row pada bulan yang sama
        tidak menambah repeat_count.
        """

        # ======================================================
        # LOCATION MONTH
        #
        # Dibuat sebagai CTE berulang pada query-query berikut.
        # ======================================================

        frequency_sql = """
            WITH location_month AS (
                SELECT DISTINCT
                    CAST(
                        LOCATION_CODE AS VARCHAR
                    ) AS locationcode,

                    CAST(
                        MONTH AS VARCHAR
                    ) AS month_key

                FROM fact_anev

                WHERE
                    LOCATION_CODE IS NOT NULL
                    AND MONTH IS NOT NULL
                    AND CAST(MONTH AS VARCHAR) <= ?
            ),

            location_frequency AS (
                SELECT
                    locationcode,
                    COUNT(*) AS months_seen

                FROM location_month

                GROUP BY
                    locationcode
            )

            SELECT
                months_seen AS repeat_count,
                COUNT(*) AS locations

            FROM location_frequency

            GROUP BY
                months_seen

            ORDER BY
                repeat_count ASC
        """

        frequency_rows = conn.execute(
            frequency_sql,
            [month_key],
        ).fetchall()

        frequency = [
            {
                "repeat_count": int(
                    row[0] or 0
                ),
                "locations": int(
                    row[1] or 0
                ),
            }
            for row in frequency_rows
        ]

        # ======================================================
        # TOTAL UNIQUE LOCATIONS
        # ======================================================

        total_sql = """
            SELECT
                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                )

            FROM fact_anev

            WHERE
                LOCATION_CODE IS NOT NULL
                AND MONTH IS NOT NULL
                AND CAST(MONTH AS VARCHAR) <= ?
        """

        total_row = conn.execute(
            total_sql,
            [month_key],
        ).fetchone()

        total_locations = (
            int(total_row[0] or 0)
            if total_row
            else 0
        )

        # ======================================================
        # REPEAT LOCATIONS + OCCURRENCES
        # ======================================================

        repeat_sql = """
            WITH location_month AS (
                SELECT DISTINCT
                    CAST(
                        LOCATION_CODE AS VARCHAR
                    ) AS locationcode,

                    CAST(
                        MONTH AS VARCHAR
                    ) AS month_key

                FROM fact_anev

                WHERE
                    LOCATION_CODE IS NOT NULL
                    AND MONTH IS NOT NULL
                    AND CAST(MONTH AS VARCHAR) <= ?
            ),

            location_frequency AS (
                SELECT
                    locationcode,
                    COUNT(*) AS months_seen

                FROM location_month

                GROUP BY
                    locationcode
            )

            SELECT
                COUNT(*) AS repeat_locations,

                COALESCE(
                    SUM(
                        months_seen - 1
                    ),
                    0
                ) AS repeat_occurrences

            FROM location_frequency

            WHERE
                months_seen > 1
        """

        repeat_row = conn.execute(
            repeat_sql,
            [month_key],
        ).fetchone()

        repeat_locations = (
            int(repeat_row[0] or 0)
            if repeat_row
            else 0
        )

        repeat_occurrences = (
            int(repeat_row[1] or 0)
            if repeat_row
            else 0
        )

        repeat_rate_pct = (
            round(
                repeat_locations
                / total_locations
                * 100,
                2,
            )
            if total_locations
            else 0.0
        )

        # ======================================================
        # REPEAT BY CLASSIFICATION
        # ======================================================

        classification_sql = """
            WITH location_month_classification AS (
                SELECT DISTINCT
                    CAST(
                        LOCATION_CODE AS VARCHAR
                    ) AS locationcode,

                    CAST(
                        MONTH AS VARCHAR
                    ) AS month_key,

                    CAST(
                        SUSPECT_NAME AS VARCHAR
                    ) AS classification

                FROM fact_anev

                WHERE
                    LOCATION_CODE IS NOT NULL
                    AND MONTH IS NOT NULL
                    AND SUSPECT_NAME IS NOT NULL
                    AND CAST(MONTH AS VARCHAR) <= ?
            ),

            classification_frequency AS (
                SELECT
                    classification,
                    locationcode,
                    COUNT(*) AS months_seen

                FROM location_month_classification

                GROUP BY
                    classification,
                    locationcode
            )

            SELECT
                classification,

                COUNT(*) AS total_locations,

                COUNT(
                    CASE
                        WHEN months_seen > 1
                        THEN 1
                    END
                ) AS repeat_locations,

                COALESCE(
                    SUM(
                        CASE
                            WHEN months_seen > 1
                            THEN months_seen - 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS repeat_occurrences

            FROM classification_frequency

            GROUP BY
                classification

            ORDER BY
                repeat_locations DESC,
                total_locations DESC
        """

        classification_rows = conn.execute(
            classification_sql,
            [month_key],
        ).fetchall()

        classifications = [
            {
                "classification": row[0],
                "total_locations": int(
                    row[1] or 0
                ),
                "repeat_locations": int(
                    row[2] or 0
                ),
                "repeat_occurrences": int(
                    row[3] or 0
                ),
            }
            for row in classification_rows
        ]

        result["pasca_repeat"] = {
            "total_locations": total_locations,
            "repeat_locations": repeat_locations,
            "repeat_occurrences": repeat_occurrences,
            "repeat_rate_pct": repeat_rate_pct,
            "frequency": frequency,
            "classification": classifications,
        }

        # ======================================================
        # COMPATIBILITY repeat_cases
        #
        # Hanya repeat > 1.
        # ======================================================

        result["repeat_cases"] = [
            {
                "label": str(
                    row["repeat_count"]
                ),
                "value": row["locations"],
            }
            for row in frequency
            if row["repeat_count"] > 1
        ]

    # ==========================================================
    # DATA SCIENCE / ANALYTICAL LAYER
    # ==========================================================

    def _load_data_science(
        self,
        conn,
        month_key: str,
        result: dict[str, Any],
    ) -> None:
        """
        Build analytical metrics for the Executive Dashboard.

        Important distinction:
        - fact_anev = suspect / ANEV population.
        - fact_pengecekan = inspection execution.
        - PRA = selected month only.
        - PASCA = historical recurrence up to selected month.

        This layer intentionally does not invent machine-learning results.
        Empty correlation / regression / feature-importance arrays remain empty
        until a real statistical model is introduced.
        """

        data_science = result["data_science"]

        # ----------------------------------------------------------
        # 1. PRA vs PASCA classification comparison
        # ----------------------------------------------------------
        pra_sql = """
            SELECT
                CAST(SUSPECT_NAME AS VARCHAR) AS classification,
                COUNT(
                    DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                ) AS total
            FROM fact_anev
            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND SUSPECT_NAME IS NOT NULL
            GROUP BY SUSPECT_NAME
        """

        pra_rows = conn.execute(
            pra_sql,
            [month_key],
        ).fetchall()

        pra_map = {
            str(row[0]): int(row[1] or 0)
            for row in pra_rows
        }

        pasca_sql = """
            WITH location_month_classification AS (
                SELECT DISTINCT
                    CAST(LOCATION_CODE AS VARCHAR) AS locationcode,
                    CAST(MONTH AS VARCHAR) AS month_key,
                    CAST(SUSPECT_NAME AS VARCHAR) AS classification
                FROM fact_anev
                WHERE
                    LOCATION_CODE IS NOT NULL
                    AND MONTH IS NOT NULL
                    AND SUSPECT_NAME IS NOT NULL
                    AND CAST(MONTH AS VARCHAR) <= ?
            )
            SELECT
                classification,
                COUNT(DISTINCT locationcode) AS total
            FROM location_month_classification
            GROUP BY classification
        """

        pasca_rows = conn.execute(
            pasca_sql,
            [month_key],
        ).fetchall()

        pasca_map = {
            str(row[0]): int(row[1] or 0)
            for row in pasca_rows
        }

        all_classifications = sorted(
            set(pra_map) | set(pasca_map)
        )

        data_science["pra_pasca_classification"] = [
            {
                "customer_type": "PRA",
                "classification": classification,
                "total": pra_map.get(classification, 0),
            }
            for classification in all_classifications
        ] + [
            {
                "customer_type": "PASCA",
                "classification": classification,
                "total": pasca_map.get(classification, 0),
            }
            for classification in all_classifications
        ]

        # ----------------------------------------------------------
        # 2. Classification priority
        #
        # Priority is an analytical ranking, not a fabricated ML score.
        # It combines:
        #   - PRA volume
        #   - PASCA volume
        #   - repeat locations
        # ----------------------------------------------------------
        repeat_by_classification = {
            item["classification"]: item
            for item in result["pasca_repeat"].get(
                "classification",
                [],
            )
        }

        priority_rows = []

        for classification in all_classifications:
            pra_total = pra_map.get(classification, 0)
            pasca_total = pasca_map.get(classification, 0)

            repeat_item = repeat_by_classification.get(
                classification,
                {},
            )

            repeat_locations = int(
                repeat_item.get("repeat_locations", 0)
            )

            repeat_occurrences = int(
                repeat_item.get("repeat_occurrences", 0)
            )

            # A transparent composite index:
            # 40% PRA share + 40% PASCA share + 20% repeat share.
            # This is explicitly a prioritisation index, not ML.
            pra_share = (
                pra_total / max(
                    result["pra_monthly"].get(
                        "total_locations",
                        0,
                    ),
                    1,
                )
            )

            pasca_share = (
                pasca_total / max(
                    result["pasca_repeat"].get(
                        "total_locations",
                        0,
                    ),
                    1,
                )
            )

            repeat_share = (
                repeat_locations / max(
                    pasca_total,
                    1,
                )
            )

            priority_score = (
                pra_share * 40.0
                + pasca_share * 40.0
                + repeat_share * 20.0
            )

            priority_rows.append(
                {
                    "classification": classification,
                    "pra_total": pra_total,
                    "pasca_total": pasca_total,
                    "repeat_locations": repeat_locations,
                    "repeat_occurrences": repeat_occurrences,
                    "priority_score": round(
                        priority_score,
                        4,
                    ),
                }
            )

        priority_rows.sort(
            key=lambda item: (
                item["priority_score"],
                item["pasca_total"],
                item["repeat_locations"],
            ),
            reverse=True,
        )

        data_science["priority_by_classification"] = (
            priority_rows
        )

        # ----------------------------------------------------------
        # 3. Unitap concentration
        # ----------------------------------------------------------
        unitap_sql = """
            SELECT
                CAST(UNITAP AS VARCHAR) AS unitap,
                COUNT(
                    DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                ) AS locations
            FROM fact_anev
            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND LOCATION_CODE IS NOT NULL
                AND UNITAP IS NOT NULL
            GROUP BY UNITAP
            ORDER BY locations DESC
        """

        unitap_rows = conn.execute(
            unitap_sql,
            [month_key],
        ).fetchall()

        pra_total_locations = max(
            result["pra_monthly"].get(
                "total_locations",
                0,
            ),
            1,
        )

        concentration = []

        for row in unitap_rows:
            unitap = str(row[0])
            locations = int(row[1] or 0)

            concentration.append(
                {
                    "unitap": unitap,
                    "locations": locations,
                    "share_pct": round(
                        locations
                        / pra_total_locations
                        * 100,
                        2,
                    ),
                }
            )

        data_science["concentration"] = {
            "unitap": concentration,
            "top_unitap": (
                concentration[0]
                if concentration
                else None
            ),
            "top_3_share_pct": round(
                sum(
                    item["share_pct"]
                    for item in concentration[:3]
                ),
                2,
            ),
        }

        # ----------------------------------------------------------
        # 4. Unitap priority
        #
        # Combines current PRA population and repeat intensity.
        # ----------------------------------------------------------
        pasca_unitap_sql = """
            WITH location_month AS (
                SELECT DISTINCT
                    CAST(LOCATION_CODE AS VARCHAR) AS locationcode,
                    CAST(MONTH AS VARCHAR) AS month_key,
                    CAST(UNITAP AS VARCHAR) AS unitap
                FROM fact_anev
                WHERE
                    LOCATION_CODE IS NOT NULL
                    AND MONTH IS NOT NULL
                    AND UNITAP IS NOT NULL
                    AND CAST(MONTH AS VARCHAR) <= ?
            ),
            location_frequency AS (
                SELECT
                    locationcode,
                    unitap,
                    COUNT(*) AS months_seen
                FROM location_month
                GROUP BY
                    locationcode,
                    unitap
            )
            SELECT
                unitap,
                COUNT(*) AS locations,
                COUNT(
                    CASE
                        WHEN months_seen > 1
                        THEN 1
                    END
                ) AS repeat_locations,
                COALESCE(
                    SUM(
                        CASE
                            WHEN months_seen > 1
                            THEN months_seen - 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS repeat_occurrences
            FROM location_frequency
            GROUP BY unitap
            ORDER BY locations DESC
        """

        pasca_unitap_rows = conn.execute(
            pasca_unitap_sql,
            [month_key],
        ).fetchall()

        pra_unitap_map = {
            str(row[0]): int(row[1] or 0)
            for row in unitap_rows
        }

        unitap_priority = []

        for row in pasca_unitap_rows:
            unitap = str(row[0])
            pasca_locations = int(row[1] or 0)
            repeat_locations = int(row[2] or 0)
            repeat_occurrences = int(row[3] or 0)
            pra_locations = pra_unitap_map.get(
                unitap,
                0,
            )

            pra_share = (
                pra_locations / pra_total_locations
            )

            repeat_rate = (
                repeat_locations
                / max(pasca_locations, 1)
            )

            score = (
                pra_share * 60.0
                + repeat_rate * 40.0
            )

            unitap_priority.append(
                {
                    "unitap": unitap,
                    "pra_locations": pra_locations,
                    "pasca_locations": pasca_locations,
                    "repeat_locations": repeat_locations,
                    "repeat_occurrences": repeat_occurrences,
                    "repeat_rate_pct": round(
                        repeat_rate * 100,
                        2,
                    ),
                    "priority_score": round(
                        score,
                        4,
                    ),
                }
            )

        unitap_priority.sort(
            key=lambda item: (
                item["priority_score"],
                item["pra_locations"],
                item["repeat_locations"],
            ),
            reverse=True,
        )

        data_science["priority_by_unitap"] = (
            unitap_priority
        )

        # ----------------------------------------------------------
        # 5. Repeat intensity
        # ----------------------------------------------------------
        total_pasca = int(
            result["pasca_repeat"].get(
                "total_locations",
                0,
            )
        )

        repeat_locations = int(
            result["pasca_repeat"].get(
                "repeat_locations",
                0,
            )
        )

        repeat_occurrences = int(
            result["pasca_repeat"].get(
                "repeat_occurrences",
                0,
            )
        )

        data_science["repeat_intensity"] = {
            "total_locations": total_pasca,
            "repeat_locations": repeat_locations,
            "repeat_occurrences": repeat_occurrences,
            "repeat_rate_pct": (
                round(
                    repeat_locations
                    / total_pasca
                    * 100,
                    2,
                )
                if total_pasca
                else 0.0
            ),
            "avg_repeat_occurrences_per_repeat_location": (
                round(
                    repeat_occurrences
                    / repeat_locations,
                    2,
                )
                if repeat_locations
                else 0.0
            ),
            "max_repeat_count": max(
                (
                    item["repeat_count"]
                    for item in result[
                        "pasca_repeat"
                    ].get("frequency", [])
                ),
                default=0,
            ),
        }

        # ----------------------------------------------------------
        # 6. Inspection coverage
        #
        # Uses the same inspection definition as get_kpis().
        # ----------------------------------------------------------
        if dataset_exists("fact_pengecekan"):
            inspection_sql = """
                WITH suspect_locations AS (
                    SELECT DISTINCT
                        CAST(LOCATION_CODE AS VARCHAR) AS IDPEL
                    FROM fact_anev
                    WHERE
                        CAST(MONTH AS VARCHAR) = ?
                        AND LOCATION_CODE IS NOT NULL
                ),
                latest_inspection AS (
                    SELECT
                        CAST(IDPEL AS VARCHAR) AS IDPEL,
                        STATUS_KWH,
                        UPDATE_STATUS,
                        WAKTU_PERIKSA,
                        ROW_NUMBER() OVER (
                            PARTITION BY CAST(IDPEL AS VARCHAR)
                            ORDER BY
                                WAKTU_PERIKSA DESC NULLS LAST
                        ) AS RN
                    FROM fact_pengecekan
                    WHERE IDPEL IS NOT NULL
                ),
                inspected AS (
                    SELECT
                        s.IDPEL,
                        p.STATUS_KWH,
                        p.UPDATE_STATUS
                    FROM suspect_locations s
                    INNER JOIN latest_inspection p
                        ON s.IDPEL = p.IDPEL
                        AND p.RN = 1
                )
                SELECT
                    COUNT(*) AS inspected,
                    COUNT(
                        CASE
                            WHEN UPPER(
                                COALESCE(
                                    STATUS_KWH,
                                    UPDATE_STATUS,
                                    ''
                                )
                            ) LIKE '%NORMAL%'
                            THEN 1
                        END
                    ) AS normal,
                    COUNT(
                        CASE
                            WHEN UPPER(
                                COALESCE(
                                    STATUS_KWH,
                                    UPDATE_STATUS,
                                    ''
                                )
                            ) NOT LIKE '%NORMAL%'
                            THEN 1
                        END
                    ) AS findings
                FROM inspected
            """

            inspection_row = conn.execute(
                inspection_sql,
                [month_key],
            ).fetchone()

            inspected = int(
                inspection_row[0] or 0
            ) if inspection_row else 0

            normal = int(
                inspection_row[1] or 0
            ) if inspection_row else 0

            findings = int(
                inspection_row[2] or 0
            ) if inspection_row else 0

            coverage_pct = (
                inspected
                / pra_total_locations
                * 100
                if pra_total_locations
                else 0.0
            )

            finding_rate_pct = (
                findings
                / inspected
                * 100
                if inspected
                else 0.0
            )

            data_science["inspection_coverage"] = {
                "total_population": (
                    pra_total_locations
                    if pra_total_locations > 0
                    else 0
                ),
                "inspected": inspected,
                "remaining": max(
                    pra_total_locations - inspected,
                    0,
                ),
                "normal": normal,
                "findings": findings,
                "coverage_pct": round(
                    coverage_pct,
                    2,
                ),
                "finding_rate_pct": round(
                    finding_rate_pct,
                    2,
                ),
            }
        else:
            data_science["inspection_coverage"] = {
                "total_population": (
                    pra_total_locations
                    if pra_total_locations > 0
                    else 0
                ),
                "inspected": 0,
                "remaining": (
                    pra_total_locations
                    if pra_total_locations > 0
                    else 0
                ),
                "normal": 0,
                "findings": 0,
                "coverage_pct": 0.0,
                "finding_rate_pct": 0.0,
            }

        # ----------------------------------------------------------
        # 7. REAL STATISTICAL ANALYTICS
        # ----------------------------------------------------------
        #
        # Do NOT fabricate correlation / regression / feature importance.
        # Calculate them from fact_anev using one observation per
        # LOCATION_CODE for the selected month.
        #
        # The helper:
        #   - discovers numeric ANEV measurement columns,
        #   - aggregates each feature with AVG per LOCATION_CODE,
        #   - uses suspect_record_count as the target,
        #   - calculates Pearson correlation + p-value,
        #   - calculates simple linear regression + R² + p-value,
        #   - calculates Random Forest feature importance when sklearn exists.
        #
        # This is the reason the Data Science cards are no longer forced to
        # show "Belum ada data".
        # ----------------------------------------------------------
        statistical = self._calculate_statistical_data_science(
            conn,
            month_key,
        )

        data_science["correlation"] = statistical["correlation"]
        data_science["linear_regression"] = statistical[
            "linear_regression"
        ]
        data_science["feature_importance"] = statistical[
            "feature_importance"
        ]


    # ==========================================================
    # HEATMAP
    # ==========================================================

    def _load_heatmap(
        self,
        conn,
        month_key: str,
        result: dict[str, Any],
    ) -> None:
        """
        UNITAP x suspect classification.

        Selected month only.

        LOCATION_CODE dihitung DISTINCT.
        """

        heatmap_sql = """
            SELECT
                CAST(
                    UNITAP AS VARCHAR
                ) AS unitap,

                CAST(
                    SUSPECT_NAME AS VARCHAR
                ) AS category,

                COUNT(
                    DISTINCT CAST(
                        LOCATION_CODE AS VARCHAR
                    )
                ) AS value

            FROM fact_anev

            WHERE
                CAST(MONTH AS VARCHAR) = ?
                AND UNITAP IS NOT NULL
                AND SUSPECT_NAME IS NOT NULL
                AND LOCATION_CODE IS NOT NULL

            GROUP BY
                UNITAP,
                SUSPECT_NAME

            ORDER BY
                UNITAP,
                value DESC
        """

        rows = conn.execute(
            heatmap_sql,
            [month_key],
        ).fetchall()

        result["heatmap_unitap_x_category"] = [
            {
                "unitap": row[0],
                "category": row[1],
                "value": int(row[2] or 0),
            }
            for row in rows
        ]

    # ==========================================================
    # DATA SCIENCE / STATISTICAL HELPERS
    # ==========================================================

    def _calculate_statistical_data_science(
        self,
        conn,
        month_key: str,
    ) -> dict[str, Any]:
        """
        Calculate real statistical relationships from fact_anev.

        Statistical unit:
            one row per LOCATION_CODE for the selected month.

        Feature:
            AVG(feature) across measurement rows belonging to the same
            LOCATION_CODE.

        Target:
            number of distinct SUSPECT_NAME classifications for that
            LOCATION_CODE in the selected month.

        This avoids pseudo-replication caused by treating every
        measurement row as an independent customer/location observation
        and gives the model a target that represents suspect diversity
        at location level rather than raw measurement-row volume.
        """
        empty = {
            "correlation": [],
            "linear_regression": [],
            "feature_importance": [],
        }

        if not month_key:
            return empty

        try:
            numeric_columns = self._get_numeric_feature_columns(conn)

            if not numeric_columns:
                logger.warning(
                    "Executive Data Science: no numeric feature columns "
                    "found in fact_anev."
                )
                return empty

            logger.info(
                "Executive Data Science: month=%s numeric_features=%s",
                month_key,
                numeric_columns,
            )

            # Build a safe aggregate query from actual DESCRIBE output.
            # Every numeric feature is aggregated before GROUP BY.
            feature_select = ",\n".join(
                (
                    "AVG(TRY_CAST("
                    + self._quote_identifier(column)
                    + " AS DOUBLE)) AS "
                    + self._quote_identifier(column)
                )
                for column in numeric_columns
            )

            sql = f"""
                SELECT
                    CAST(LOCATION_CODE AS VARCHAR) AS locationcode,
                    COUNT(
                        DISTINCT CAST(SUSPECT_NAME AS VARCHAR)
                    ) AS suspect_classification_count,
                    {feature_select}
                FROM fact_anev
                WHERE
                    CAST(MONTH AS VARCHAR) = ?
                    AND LOCATION_CODE IS NOT NULL
                GROUP BY LOCATION_CODE
                HAVING COUNT(DISTINCT SUSPECT_NAME) > 0
            """

            rows = conn.execute(
                sql,
                [str(month_key)],
            ).fetchall()

            logger.info(
                "Executive Data Science: month=%s location_observations=%d",
                month_key,
                len(rows),
            )

            if len(rows) < 3:
                logger.warning(
                    "Executive Data Science skipped: only %d "
                    "location observations for month %s.",
                    len(rows),
                    month_key,
                )
                return empty

            try:
                import numpy as np
            except ImportError:
                logger.warning(
                    "numpy is unavailable; Executive statistical "
                    "analytics skipped."
                )
                return empty

            target = np.asarray(
                [
                    self._to_float(row[1])
                    for row in rows
                ],
                dtype=float,
            )

            feature_arrays: dict[str, Any] = {}

            for index, column in enumerate(numeric_columns):
                feature_arrays[column] = np.asarray(
                    [
                        self._to_float(row[index + 2])
                        for row in rows
                    ],
                    dtype=float,
                )

            target_name = "suspect_classification_count"

            correlations: list[dict[str, Any]] = []
            regressions: list[dict[str, Any]] = []
            usable_features: list[tuple[str, Any]] = []

            # scipy gives us reliable p-values.  If it is not installed,
            # we still calculate r / regression / R² using numpy and mark
            # p-values as None rather than inventing significance.
            try:
                from scipy.stats import linregress, pearsonr
            except ImportError:
                linregress = None
                pearsonr = None
                logger.warning(
                    "scipy is unavailable; p-values will be omitted."
                )

            for column, values in feature_arrays.items():
                mask = (
                    np.isfinite(values)
                    & np.isfinite(target)
                )

                x = values[mask]
                y = target[mask]

                if len(x) < 3:
                    continue

                if np.ptp(x) == 0:
                    continue

                if np.ptp(y) == 0:
                    continue

                try:
                    # Pearson r.
                    if pearsonr is not None:
                        correlation_value, correlation_p = pearsonr(
                            x,
                            y,
                        )
                        correlation_p = float(correlation_p)
                    else:
                        correlation_value = float(
                            np.corrcoef(x, y)[0, 1]
                        )
                        correlation_p = None

                    # Simple linear regression.
                    if linregress is not None:
                        regression = linregress(x, y)
                        slope = float(regression.slope)
                        intercept = float(regression.intercept)
                        r_value = float(regression.rvalue)
                        regression_p = float(regression.pvalue)
                    else:
                        slope, intercept = np.polyfit(
                            x,
                            y,
                            1,
                        )
                        r_value = float(
                            np.corrcoef(x, y)[0, 1]
                        )
                        regression_p = None

                    r_squared = float(r_value ** 2)

                except Exception:
                    logger.exception(
                        "Statistical calculation failed for "
                        "Executive feature %s.",
                        column,
                    )
                    continue

                correlations.append(
                    {
                        "feature_x": column,
                        "feature_y": target_name,
                        "correlation": round(
                            float(correlation_value),
                            6,
                        ),
                        "abs_correlation": round(
                            abs(float(correlation_value)),
                            6,
                        ),
                        "p_value": (
                            round(correlation_p, 8)
                            if correlation_p is not None
                            else None
                        ),
                        "sample_size": int(len(x)),
                        "significant": (
                            bool(correlation_p <= 0.05)
                            if correlation_p is not None
                            else None
                        ),
                    }
                )

                regressions.append(
                    {
                        "feature": column,
                        "target": target_name,
                        "slope": round(
                            slope,
                            8,
                        ),
                        "intercept": round(
                            intercept,
                            8,
                        ),
                        "r_squared": round(
                            r_squared,
                            8,
                        ),
                        "sample_size": int(len(x)),
                        "p_value": (
                            round(regression_p, 8)
                            if regression_p is not None
                            else None
                        ),
                        "significant": (
                            bool(regression_p <= 0.05)
                            if regression_p is not None
                            else None
                        ),
                    }
                )

                usable_features.append(
                    (
                        column,
                        values,
                    )
                )

            correlations.sort(
                key=lambda item: float(
                    item["abs_correlation"]
                ),
                reverse=True,
            )

            regressions.sort(
                key=lambda item: float(
                    item["r_squared"]
                ),
                reverse=True,
            )

            # Keep the API compact and deterministic.
            correlations = correlations[:10]
            regressions = regressions[:10]

            feature_importance: list[dict[str, Any]] = []

            # ------------------------------------------------------
            # Random Forest feature importance
            # ------------------------------------------------------
            try:
                from sklearn.ensemble import RandomForestRegressor

                if usable_features:
                    valid_columns: list[str] = []
                    x_columns: list[Any] = []

                    for column, values in usable_features:
                        clean = values[np.isfinite(values)]

                        if clean.size < 3:
                            continue

                        # Median imputation retains locations where a
                        # numeric field is NULL for only some measurements.
                        median = float(np.median(clean))

                        imputed = np.where(
                            np.isfinite(values),
                            values,
                            median,
                        )

                        valid_columns.append(column)
                        x_columns.append(imputed)

                    if x_columns:
                        X = np.column_stack(x_columns)

                        valid_y = np.isfinite(target)
                        X = X[valid_y]
                        y = target[valid_y]

                        if (
                            X.shape[0] >= 3
                            and X.shape[1] > 0
                            and np.ptp(y) > 0
                        ):
                            model = RandomForestRegressor(
                                n_estimators=300,
                                random_state=42,
                                n_jobs=-1,
                            )

                            model.fit(X, y)

                            correlation_lookup = {
                                item["feature_x"]: item
                                for item in correlations
                            }

                            feature_importance = [
                                {
                                    "feature": feature,
                                    "target": target_name,
                                    "importance": round(
                                        float(importance),
                                        8,
                                    ),
                                    "direction": (
                                        "positive"
                                        if float(
                                            correlation_lookup.get(
                                                feature,
                                                {
                                                    "correlation": 0,
                                                },
                                            ).get(
                                                "correlation",
                                                0,
                                            )
                                        ) >= 0
                                        else "negative"
                                    ),
                                    "correlation": (
                                        float(
                                            correlation_lookup[
                                                feature
                                            ]["correlation"]
                                        )
                                        if feature
                                        in correlation_lookup
                                        else None
                                    ),
                                }
                                for feature, importance in zip(
                                    valid_columns,
                                    model.feature_importances_,
                                )
                            ]

                            feature_importance.sort(
                                key=lambda item: float(
                                    item["importance"]
                                ),
                                reverse=True,
                            )

                            feature_importance = (
                                feature_importance[:10]
                            )

            except ImportError:
                logger.warning(
                    "scikit-learn is unavailable; Executive "
                    "feature importance skipped."
                )

            except Exception:
                logger.exception(
                    "Failed to calculate Executive feature importance."
                )

            logger.info(
                "Executive statistical analytics: month=%s "
                "correlations=%d regressions=%d features=%d",
                month_key,
                len(correlations),
                len(regressions),
                len(feature_importance),
            )

            return {
                "correlation": correlations,
                "linear_regression": regressions,
                "feature_importance": feature_importance,
            }

        except Exception:
            logger.exception(
                "Failed to calculate Executive statistical analytics "
                "for month %s.",
                month_key,
            )
            return empty

    @staticmethod
    def _quote_identifier(
        identifier: str,
    ) -> str:
        """Safely quote a DuckDB identifier."""
        return '"' + str(identifier).replace(
            '"',
            '""',
        ) + '"'

    @staticmethod
    def _to_float(
        value: Any,
    ) -> float:
        """Convert a DB value to float; invalid values become NaN."""
        if value is None:
            return float("nan")

        try:
            return float(value)
        except (TypeError, ValueError):
            return float("nan")

    @classmethod
    def _get_numeric_feature_columns(
        cls,
        conn,
    ) -> list[str]:
        """
        Discover actual numeric measurement columns in fact_anev.

        Identifier, month, year and coordinate/key fields are excluded.
        The result is capped for predictable dashboard/API performance.
        """
        try:
            rows = conn.execute(
                "DESCRIBE fact_anev"
            ).fetchall()
        except Exception:
            logger.exception(
                "Failed to inspect fact_anev schema for "
                "Data Science features."
            )
            return []

        excluded_exact = {
            "LOCATION_CODE",
            "LOCATIONCODE",
            "IDPEL",
            "MONTH",
            "YEAR",
        }

        excluded_coordinate_names = {
            "LATITUDE",
            "LONGITUDE",
            "LAT",
            "LON",
            "LONG",
            "X",
            "Y",
        }

        numeric_tokens = (
            "TINYINT",
            "SMALLINT",
            "INTEGER",
            "BIGINT",
            "HUGEINT",
            "UTINYINT",
            "USMALLINT",
            "UINTEGER",
            "UBIGINT",
            "UHUGEINT",
            "DECIMAL",
            "NUMERIC",
            "FLOAT",
            "DOUBLE",
            "REAL",
        )

        columns: list[str] = []

        for row in rows:
            if not row:
                continue

            name = str(row[0])
            data_type = str(
                row[1] or ""
            ).upper()

            upper_name = name.upper()

            if upper_name in excluded_exact:
                continue

            if upper_name in excluded_coordinate_names:
                continue

            # Do not accidentally treat ID-like fields as explanatory
            # measurements.
            if (
                upper_name.startswith("ID_")
                or upper_name.endswith("_ID")
            ):
                continue

            if not any(
                token in data_type
                for token in numeric_tokens
            ):
                continue

            columns.append(name)

        return columns[:20]

    # ==========================================================
    # FACT CHECK
    # ==========================================================

    @staticmethod
    def _fact_anev_exists(
        conn,
    ) -> bool:
        """
        Lightweight check for fact_anev.
        """

        try:
            conn.execute(
                "SELECT 1 FROM fact_anev LIMIT 1"
            ).fetchone()

            return True

        except Exception:
            return False