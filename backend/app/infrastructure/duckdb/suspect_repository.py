"""DuckDB-backed implementation of SuspectRepository."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.month_utils import month_keys_to_options
from app.domain.entities import MonthOption, PageResult
from app.infrastructure.duckdb.connection import (
    dataset_exists,
    get_connection,
    list_month_partitions,
    read_dataset_sql,
)
from app.infrastructure.duckdb.query_helpers import (
    build_equality_filters,
    build_search_clause,
    paginate,
)


_DETAIL_FILTER_COLUMN_MAP = {
    "unitupi": "UNITUPI",
    "unitap": "UNITAP",
    "unitup": "UNITUP",
    "tariff": "TARIFF",
    "suspect_name": "SUSPECT_NAME",
    "location_code": "LOCATION_CODE",
}


_SUMMARY_FILTER_COLUMN_MAP = {
    "unitupi": "UNITUPI",
    "unitap": "UNITAP",
    "unitup": "UNITUP",
    "tariff": "TARIFF",
}


class DuckDbSuspectRepository:

    # ==========================================================
    # MONTH
    # ==========================================================

    def get_available_months(
        self,
    ) -> list[MonthOption]:
        """Return every month actually available in the Suspect data.

        ``suspect_detail`` is a measurement/detail dataset and can lag behind
        ``fact_anev``.  Suspect Analytics, classification, repeat analysis,
        and the map are driven by ``fact_anev``, so the month selector must be
        sourced from the same fact table.

        The fallback to ``suspect_detail`` keeps the endpoint usable when an
        ANEV fact table has not been materialized yet.
        """
        conn = get_connection()

        try:
            if dataset_exists("fact_anev"):
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

                if months:
                    return month_keys_to_options(months)

            # Fallback for installations where fact_anev is not available.
            if dataset_exists("suspect_detail"):
                return month_keys_to_options(
                    list_month_partitions("suspect_detail")
                )

            return []

        finally:
            conn.close()

    # ==========================================================
    # DASHBOARD / ANALYTICS COMPATIBILITY
    # ==========================================================

    def get_dashboard(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the complete Suspect dashboard payload.

        This method is kept as the repository-level compatibility entry point
        required by the domain protocol.  The HTTP analytics endpoint uses
        the more focused use-cases, but older callers can use this method
        without triggering an AttributeError.
        """
        filters = filters or {}

        anev = self.get_anev_summary(
            month_key,
            filters,
        )

        repeat = self.get_repeat_summary(
            month_key,
        )

        return {
            "anev": anev,
            "pasca_repeat": repeat,
            "repeat_cases": [
                {
                    "label": str(item["repeat_count"]),
                    "value": int(item["locations"]),
                }
                for item in repeat.get("frequency", [])
                if int(item.get("repeat_count", 0)) > 1
            ],
            "classification": anev.get(
                "classification",
                [],
            ),
        }


    # ==========================================================
    # MAIN
    # ==========================================================

    def get_main(
        self,
        month_key: str,
        page: int,
        page_size: int,
        search: str | None,
    ) -> PageResult:

        if not dataset_exists(
            "suspect_main"
        ):
            return PageResult(
                items=[],
                total_rows=0,
                page=page,
                page_size=page_size,
            )

        settings = get_settings()
        conn = get_connection()

        try:

            offset, page_size = paginate(
                page,
                page_size,
                settings.MAX_PAGE_SIZE,
            )

            search_sql, search_params = (
                build_search_clause(
                    search,
                    ["SUSPECT_NAME"],
                )
            )

            from_clause = read_dataset_sql(
                "suspect_main",
                month_key,
            )

            where_sql = (
                f"WHERE MONTH_KEY = ? "
                f"{search_sql}"
            )

            params = [
                month_key,
                *search_params,
            ]

            total_rows = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM {from_clause}
                {where_sql}
                """,
                params,
            ).fetchone()[0]

            page_sql = f"""
                SELECT
                    SUSPECT_NAME,
                    PELANGGAN,
                    FREKUENSI
                FROM {from_clause}
                {where_sql}
                ORDER BY FREKUENSI DESC
                LIMIT ?
                OFFSET ?
            """

            rows = conn.execute(
                page_sql,
                [
                    *params,
                    page_size,
                    offset,
                ],
            ).fetchall()

            items = [
                {
                    "suspect_name": row[0],
                    "pelanggan": row[1],
                    "frekuensi": row[2],
                }
                for row in rows
            ]

            return PageResult(
                items=items,
                total_rows=total_rows,
                page=page,
                page_size=page_size,
            )

        finally:

            conn.close()

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def get_summary(
        self,
        month_key: str,
        filters: dict[str, Any],
    ) -> list[dict]:

        if not dataset_exists(
            "suspect_summary"
        ):
            return []

        conn = get_connection()

        try:

            equality_sql, equality_params = (
                build_equality_filters(
                    filters,
                    _SUMMARY_FILTER_COLUMN_MAP,
                )
            )

            search_sql = ""
            search_params: list[Any] = []

            if filters.get(
                "search_customer"
            ):

                (
                    search_sql,
                    search_params,
                ) = build_search_clause(
                    filters[
                        "search_customer"
                    ],
                    ["LOCATION_NAME"],
                )

            sql = f"""
                SELECT *
                FROM {
                    read_dataset_sql(
                        "suspect_summary",
                        month_key,
                    )
                }
                WHERE MONTH_KEY = ?
                {equality_sql}
                {search_sql}
                ORDER BY GRAND_TOTAL DESC
            """

            cursor = conn.execute(
                sql,
                [
                    month_key,
                    *equality_params,
                    *search_params,
                ],
            )

            columns = [
                description[0]
                for description in cursor.description
            ]

            return [
                dict(
                    zip(
                        columns,
                        row,
                    )
                )
                for row in cursor.fetchall()
            ]

        finally:

            conn.close()

    # ==========================================================
    # DETAIL
    # ==========================================================

    def get_detail(
        self,
        month_key: str,
        filters: dict[str, Any],
        page: int,
        page_size: int,
    ) -> PageResult:
        """Return Suspect detail rows directly from ``fact_anev``.

        The processed installation currently materializes ANEV measurements
        in ``fact_anev``.  ``suspect_detail`` is not required for the detail
        page.

        One row in ``fact_anev`` is an ANEV measurement.  Classification,
        repeat-count, search, and organizational filters are therefore
        applied directly to the same fact table used by the analytics layer.
        """

        if not dataset_exists("fact_anev"):
            return PageResult(
                items=[],
                total_rows=0,
                page=page,
                page_size=page_size,
            )

        settings = get_settings()
        conn = get_connection()

        try:
            offset, page_size = paginate(
                page,
                page_size,
                settings.MAX_PAGE_SIZE,
            )

            filters = filters or {}

            # ----------------------------------------------------------
            # Classification normalization
            # ----------------------------------------------------------
            normalized_suspect_sql = """
                CASE
                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'ASYMMETRICPOWERBYINSTANT'
                        THEN 'ASYMMETRIC POWER BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'INCORRECTPHASEBYINSTANT'
                        THEN 'INCORRECT PHASE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'OVERCURRENTBYINSTANT'
                        THEN 'OVER CURRENT BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'OVERVOLTAGEBYINSTANT'
                        THEN 'OVER VOLTAGE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'REVERSALBYINSTANT'
                        THEN 'REVERSAL BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'TIMEDIFFERENCE-INSTANT'
                        THEN 'TIME DIFFERENCE - INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'UNBALANCECURRENTBYINSTANT'
                        THEN 'UNBALANCE CURRENT BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                                )
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'UNDERVOLTAGEBYINSTANT'
                        THEN 'UNDER VOLTAGE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(
                                UPPER(
                                    CAST(SUSPECT_NAME AS VARCHAR)
                            ),
                            '\\s+',
                            ' ',
                            'g'
                        ),
                        ' ',
                        ''
                    ) = 'VOLTAGEDIP-INSTANT'
                        THEN 'VOLTAGE DIP - INSTANT'

                    ELSE REGEXP_REPLACE(
                        TRIM(
                            UPPER(
                                CAST(SUSPECT_NAME AS VARCHAR)
                            )
                        ),
                        '\\s+',
                        ' ',
                        'g'
                    )
                END
            """

            # ----------------------------------------------------------
            # Base filters
            # ----------------------------------------------------------
            clauses = [
                "CAST(a.MONTH AS VARCHAR) = ?",
                "a.LOCATION_CODE IS NOT NULL",
                "a.SUSPECT_NAME IS NOT NULL",
            ]

            params: list[Any] = [
                str(month_key),
            ]

            for key, column in (
                ("unitupi", "UNITUPI"),
                ("unitap", "UNITAP"),
                ("unitup", "UNITUP"),
                ("tariff", "TARIFF"),
            ):
                value = filters.get(key)

                if value not in (None, ""):
                    clauses.append(
                        f"CAST(a.{column} AS VARCHAR) = ?"
                    )
                    params.append(str(value))

            # ----------------------------------------------------------
            # Classification filter
            # ----------------------------------------------------------
            selected_classification = filters.get(
                "suspect_name"
            )

            if selected_classification not in (None, ""):
                classification = " ".join(
                    str(selected_classification)
                    .strip()
                    .upper()
                    .split()
                )

                # SUSPECT_NAME may contain multiple classifications in one
                # ANEV row, e.g.
                # "ASYMMETRIC POWER BY INSTANT, OVER VOLTAGE BY INSTANT".
                # Match the selected classification as a comma-delimited
                # token instead of comparing the entire cell.
                normalized_classification_list_sql = """
                    ',' ||
                    REGEXP_REPLACE(
                        TRIM(
                            UPPER(
                                CAST(a.SUSPECT_NAME AS VARCHAR)
                            )
                        ),
                        '\\s*,\\s*',
                        ',',
                        'g'
                    ) ||
                    ','
                """

                clauses.append(
                    f"{normalized_classification_list_sql} LIKE ?"
                )
                params.append(
                    f"%,{classification},%"
                )

            # ----------------------------------------------------------
            # Search filter
            # ----------------------------------------------------------
            search_value = filters.get("search_customer")

            if search_value not in (None, ""):
                pattern = f"%{str(search_value).strip()}%"

                clauses.append(
                    """
                    (
                        CAST(a.LOCATION_CODE AS VARCHAR) ILIKE ?
                        OR CAST(a.LOCATION_NAME AS VARCHAR) ILIKE ?
                        OR CAST(a.SUSPECT_NAME AS VARCHAR) ILIKE ?
                    )
                    """
                )

                params.extend(
                    [
                        pattern,
                        pattern,
                        pattern,
                    ]
                )

            # ----------------------------------------------------------
            # Repeat filter
            # ----------------------------------------------------------
            repeat_cte = ""
            repeat_join = ""
            repeat_params: list[Any] = []

            requested_repeat = filters.get(
                "repeat_count"
            )

            if requested_repeat not in (None, ""):
                repeat_cte = """
                    repeat_locations AS (
                        SELECT
                            CAST(LOCATION_CODE AS VARCHAR)
                                AS LOCATION_CODE,

                            COUNT(
                                DISTINCT CAST(MONTH AS VARCHAR)
                            ) AS REPEAT_COUNT

                        FROM fact_anev

                        WHERE LOCATION_CODE IS NOT NULL
                          AND MONTH IS NOT NULL
                          AND CAST(MONTH AS VARCHAR) <= ?

                        GROUP BY LOCATION_CODE
                    ),
                """

                repeat_join = """
                    INNER JOIN repeat_locations rr
                        ON rr.LOCATION_CODE =
                           CAST(a.LOCATION_CODE AS VARCHAR)

                       AND rr.REPEAT_COUNT = ?
                """

                repeat_params.extend(
                    [
                        str(month_key),
                        int(requested_repeat),
                    ]
                )

            # ----------------------------------------------------------
            # Inspection lookup
            # ----------------------------------------------------------
            inspection_cte = ""
            inspection_join = ""
            inspection_params: list[Any] = []

            if dataset_exists("fact_pengecekan"):
                inspection_cte = """
                    inspection_by_idpel AS (
                        SELECT
                            REGEXP_REPLACE(
                                TRIM(
                                    CAST(IDPEL AS VARCHAR)
                                ),
                                '\\.0$',
                                ''
                            ) AS IDPEL,

                            WAKTU_PERIKSA,

                            CAST(
                                NAMA_PETUGAS AS VARCHAR
                            ) AS NAMA_PETUGAS,

                            CAST(
                                CATATAN AS VARCHAR
                            ) AS CATATAN,

                            CAST(
                                TINDAKLANJUT_PEMERIKSAAN
                                AS VARCHAR
                            ) AS TINDAKLANJUT_PEMERIKSAAN,

                            ROW_NUMBER() OVER (
                                PARTITION BY
                                    REGEXP_REPLACE(
                                        TRIM(
                                            CAST(IDPEL AS VARCHAR)
                                        ),
                                        '\\.0$',
                                        ''
                                    )
                                ORDER BY
                                    WAKTU_PERIKSA DESC NULLS LAST
                            ) AS RN

                        FROM fact_pengecekan

                        WHERE IDPEL IS NOT NULL
                          AND WAKTU_PERIKSA >=
                              TRY_CAST(? AS DATE)
                          AND WAKTU_PERIKSA <
                              DATE_ADD(
                                  TRY_CAST(? AS DATE),
                                  INTERVAL 1 MONTH
                              )
                          AND WAKTU_PERIKSA IS NOT NULL
                    ),
                """

                inspection_join = """
                    LEFT JOIN inspection_by_idpel ip
                        ON REGEXP_REPLACE(
                            TRIM(
                                CAST(a.LOCATION_CODE AS VARCHAR)
                            ),
                            '\\.0$',
                            ''
                        ) = ip.IDPEL
                       AND ip.RN = 1
                """

                month_date = (
                    f"{str(month_key)[:4]}-"
                    f"{str(month_key)[4:6]}-01"
                )

                inspection_params.extend(
                    [
                        month_date,
                        month_date,
                    ]
                )
            else:
                inspection_cte = """
                    inspection_by_idpel AS (
                        SELECT
                            CAST(NULL AS VARCHAR) AS IDPEL,
                            CAST(NULL AS TIMESTAMP)
                                AS WAKTU_PERIKSA,
                            CAST(NULL AS VARCHAR)
                                AS NAMA_PETUGAS,
                            CAST(NULL AS VARCHAR)
                                AS CATATAN,
                            CAST(NULL AS VARCHAR)
                                AS TINDAKLANJUT_PEMERIKSAAN,
                            CAST(NULL AS INTEGER) AS RN
                        WHERE FALSE
                    ),
                """

                inspection_join = """
                    LEFT JOIN inspection_by_idpel ip
                        ON FALSE
                """

            # ----------------------------------------------------------
            # Inspection status filter
            # ----------------------------------------------------------
            inspection_status = filters.get(
                "inspection_status"
            )

            normalized_status = (
                str(inspection_status)
                .strip()
                .upper()
                if inspection_status not in (None, "")
                else ""
            )

            if normalized_status == "SUDAH_PERIKSA":
                clauses.append(
                    "ip.IDPEL IS NOT NULL"
                )

            elif normalized_status == "BELUM_PERIKSA":
                clauses.append(
                    "ip.IDPEL IS NULL"
                )

            where_sql = (
                "WHERE "
                + "\nAND ".join(clauses)
            )

            cte_parts = [
                "base AS (SELECT * FROM fact_anev)"
            ]

            if repeat_cte:
                cte_parts.append(
                    repeat_cte.strip().lstrip(",").rstrip(",")
                )

            cte_parts.append(
                inspection_cte.strip().rstrip(",")
            )

            cte_sql = "WITH\n" + ",\n".join(cte_parts)

            base_params = [
                *repeat_params,
                *inspection_params,
                *params,
            ]

            # ----------------------------------------------------------
            # Total
            # ----------------------------------------------------------
            total_sql = f"""
                {cte_sql}

                SELECT COUNT(*)

                FROM base a

                {repeat_join}

                {inspection_join}

                {where_sql}
            """

            total_rows = int(
                conn.execute(
                    total_sql,
                    base_params,
                ).fetchone()[0]
                or 0
            )

            # ----------------------------------------------------------
            # Detail rows
            # ----------------------------------------------------------
            detail_sql = f"""
                {cte_sql}

                SELECT
                    a.*,

                    CASE
                        WHEN ip.IDPEL IS NOT NULL
                            THEN 'SUDAH_PERIKSA'
                        ELSE 'BELUM_PERIKSA'
                    END AS INSPECTION_STATUS,

                    ip.WAKTU_PERIKSA,
                    ip.NAMA_PETUGAS,
                    ip.CATATAN,
                    ip.TINDAKLANJUT_PEMERIKSAAN

                FROM base a

                {repeat_join}

                {inspection_join}

                {where_sql}

                ORDER BY
                    a.READ_DATE DESC NULLS LAST,
                    a.LOCATION_CODE

                LIMIT ?
                OFFSET ?
            """

            cursor = conn.execute(
                detail_sql,
                [
                    *base_params,
                    page_size,
                    offset,
                ],
            )

            columns = [
                description[0]
                for description in cursor.description
            ]

            items = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

            return PageResult(
                items=items,
                total_rows=total_rows,
                page=page,
                page_size=page_size,
            )

        finally:
            conn.close()

    # ==========================================================
    # DETAIL TREND
    # ==========================================================

    def get_detail_trend(
        self,
        month_key: str,
        location_code: str,
    ) -> dict[str, Any]:
        """Return electrical trend data directly from ``fact_anev``."""

        empty = {
            "location_code": location_code,
            "voltage_l1": [],
            "voltage_l2": [],
            "voltage_l3": [],
            "current_l1": [],
            "current_l2": [],
            "current_l3": [],
            "stats": {},
        }

        if not dataset_exists("fact_anev"):
            return empty

        conn = get_connection()

        try:
            sql = """
                SELECT
                    READ_DATE,
                    VOLTAGE_L1,
                    VOLTAGE_L2,
                    VOLTAGE_L3,
                    CURRENT_L1,
                    CURRENT_L2,
                    CURRENT_L3,
                    POWER_FACTOR_TOTAL

                FROM fact_anev

                WHERE
                    CAST(MONTH AS VARCHAR) = ?

                    AND CAST(
                        LOCATION_CODE AS VARCHAR
                    ) = ?

                ORDER BY
                    READ_DATE ASC
            """

            rows = conn.execute(
                sql,
                [
                    str(month_key),
                    str(location_code),
                ],
            ).fetchall()

            if not rows:
                return empty

            def series(
                index: int,
            ) -> list[dict]:
                return [
                    {
                        "read_date": str(row[0]),
                        "value": row[index],
                    }
                    for row in rows
                    if row[index] is not None
                ]

            pf_values = [
                row[7]
                for row in rows
                if row[7] is not None
            ]

            voltage_l1_values = [
                row[1]
                for row in rows
                if row[1] is not None
            ]

            stats = {
                "reading_count": len(rows),

                "avg_power_factor": (
                    round(
                        sum(pf_values)
                        / len(pf_values),
                        3,
                    )
                    if pf_values
                    else 0.0
                ),

                "avg_voltage_l1": (
                    round(
                        sum(voltage_l1_values)
                        / len(voltage_l1_values),
                        2,
                    )
                    if voltage_l1_values
                    else 0.0
                ),
            }

            return {
                "location_code": location_code,
                "voltage_l1": series(1),
                "voltage_l2": series(2),
                "voltage_l3": series(3),
                "current_l1": series(4),
                "current_l2": series(5),
                "current_l3": series(6),
                "stats": stats,
            }

        finally:
            conn.close()

    # ==========================================================
    # CLASSIFICATION SUMMARY
    # ==========================================================

    def get_classification_summary(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return classification counts from ``fact_anev``.

        ``fact_anev`` is a measurement-level fact table, therefore the
        classification chart counts DISTINCT LOCATION_CODE rather than raw
        measurement rows.  This keeps the chart consistent with ANEV/PRA
        totals, Executive analytics, and the repeat definition.
        """
        if not dataset_exists("fact_anev"):
            return []

        filters = filters or {}
        conn = get_connection()

        try:
            clauses = [
                "CAST(MONTH AS VARCHAR) = ?",
                "LOCATION_CODE IS NOT NULL",
                "SUSPECT_NAME IS NOT NULL",
            ]
            params: list[Any] = [str(month_key)]

            for key, column in (
                ("unitupi", "UNITUPI"),
                ("unitap", "UNITAP"),
                ("unitup", "UNITUP"),
                ("tariff", "TARIFF"),
            ):
                value = filters.get(key)
                if value not in (None, ""):
                    clauses.append(f"CAST({column} AS VARCHAR) = ?")
                    params.append(str(value))

            search_value = filters.get("search_customer")
            if search_value not in (None, ""):
                clauses.append(
                    "(CAST(LOCATION_CODE AS VARCHAR) ILIKE ? "
                    "OR CAST(LOCATION_NAME AS VARCHAR) ILIKE ?)"
                )
                pattern = f"%{str(search_value).strip()}%"
                params.extend([pattern, pattern])

            where_sql = "\n                    AND ".join(clauses)

            rows = conn.execute(
                f"""
                SELECT
                    CAST(SUSPECT_NAME AS VARCHAR) AS classification,
                    COUNT(
                        DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                    ) AS total
                FROM fact_anev
                WHERE {where_sql}
                GROUP BY SUSPECT_NAME
                ORDER BY total DESC, classification ASC
                """,
                params,
            ).fetchall()

            return [
                {
                    "classification": row[0],
                    "total": int(row[1] or 0),
                }
                for row in rows
            ]

        finally:
            conn.close()

    # ==========================================================
    # ANEV SUMMARY
    # ==========================================================

    def get_anev_summary(
        self,
        month_key: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Return ANEV analytics from fact_anev.

        ANEV is intentionally sourced from fact_anev, not suspect_detail.
        One LOCATION_CODE is counted once for the selected month.
        """

        empty = {
            "total_locations": 0,
            "total_classifications": 0,
            "classification": [],
            "unitap": [],
            "tariff": [],
        }

        if not dataset_exists("fact_anev"):
            return empty

        filters = filters or {}
        conn = get_connection()

        try:
            clauses = [
                "CAST(MONTH AS VARCHAR) = ?",
                "LOCATION_CODE IS NOT NULL",
            ]
            params: list[Any] = [str(month_key)]

            if filters.get("unitupi"):
                clauses.append(
                    "CAST(UNITUPI AS VARCHAR) = ?"
                )
                params.append(str(filters["unitupi"]))

            if filters.get("unitap"):
                clauses.append(
                    "CAST(UNITAP AS VARCHAR) = ?"
                )
                params.append(str(filters["unitap"]))

            if filters.get("unitup"):
                clauses.append(
                    "CAST(UNITUP AS VARCHAR) = ?"
                )
                params.append(str(filters["unitup"]))

            if filters.get("tariff"):
                clauses.append(
                    "CAST(TARIFF AS VARCHAR) = ?"
                )
                params.append(str(filters["tariff"]))

            where_sql = "\n                    AND ".join(clauses)

            total_row = conn.execute(
                f"""
                SELECT COUNT(
                    DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                )
                FROM fact_anev
                WHERE {where_sql}
                """,
                params,
            ).fetchone()

            total_locations = (
                int(total_row[0] or 0)
                if total_row
                else 0
            )

            classification_rows = conn.execute(
                f"""
                SELECT
                    CAST(SUSPECT_NAME AS VARCHAR) AS classification,
                    COUNT(
                        DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                    ) AS total
                FROM fact_anev
                WHERE
                    {where_sql}
                    AND SUSPECT_NAME IS NOT NULL
                GROUP BY SUSPECT_NAME
                ORDER BY total DESC
                """,
                params,
            ).fetchall()

            classification = [
                {
                    "classification": row[0],
                    "total": int(row[1] or 0),
                }
                for row in classification_rows
            ]

            unitap_rows = conn.execute(
                f"""
                SELECT
                    CAST(UNITAP AS VARCHAR) AS unitap,
                    COUNT(
                        DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                    ) AS total
                FROM fact_anev
                WHERE
                    {where_sql}
                    AND UNITAP IS NOT NULL
                GROUP BY UNITAP
                ORDER BY total DESC
                """,
                params,
            ).fetchall()

            unitap = [
                {
                    "unitap": row[0],
                    "total": int(row[1] or 0),
                }
                for row in unitap_rows
            ]

            tariff_rows = conn.execute(
                f"""
                SELECT
                    CAST(TARIFF AS VARCHAR) AS tariff,
                    COUNT(
                        DISTINCT CAST(LOCATION_CODE AS VARCHAR)
                    ) AS total
                FROM fact_anev
                WHERE
                    {where_sql}
                    AND TARIFF IS NOT NULL
                GROUP BY TARIFF
                ORDER BY total DESC
                """,
                params,
            ).fetchall()

            tariff = [
                {
                    "tariff": row[0],
                    "total": int(row[1] or 0),
                }
                for row in tariff_rows
            ]

            return {
                "total_locations": total_locations,
                "total_classifications": len(classification),
                "classification": classification,
                "unitap": unitap,
                "tariff": tariff,
            }

        finally:
            conn.close()


    # ==========================================================
    # REPEAT / FREQUENCY SUMMARY
    # ==========================================================

    def get_repeat_summary(
        self,
        month_key: str,
    ) -> dict[str, Any]:
        """
        PASCA repeat analysis from fact_anev.

        One LOCATION_CODE + one MONTH = one occurrence.
        Raw measurement rows in the same month do not increase
        the repeat count.
        """

        empty = {
            "total_customers": 0,
            "repeat_customers": 0,
            "repeat_occurrences": 0,
            "repeat_rate_pct": 0.0,
            "frequency": [],
            "by_suspect": [],
        }

        if not dataset_exists("fact_anev"):
            return empty

        conn = get_connection()

        try:
            frequency_sql = r"""
                WITH location_month AS (
                    SELECT DISTINCT
                        CAST(LOCATION_CODE AS VARCHAR) AS locationcode,
                        CAST(MONTH AS VARCHAR) AS month_key
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
                    GROUP BY locationcode
                )
                SELECT
                    months_seen AS repeat_count,
                    COUNT(*) AS locations
                FROM location_frequency
                GROUP BY months_seen
                ORDER BY repeat_count ASC
            """

            frequency_rows = conn.execute(
                frequency_sql,
                [str(month_key)],
            ).fetchall()

            frequency = [
                {
                    "repeat_count": int(row[0] or 0),
                    "locations": int(row[1] or 0),
                }
                for row in frequency_rows
                if row[0] is not None
            ]

            total_customers = sum(
                item["locations"]
                for item in frequency
            )

            repeat_customers = sum(
                item["locations"]
                for item in frequency
                if item["repeat_count"] > 1
            )

            repeat_occurrences = sum(
                (
                    item["repeat_count"] - 1
                ) * item["locations"]
                for item in frequency
                if item["repeat_count"] > 1
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

            by_suspect_sql = r"""
                WITH location_month_classification AS (
                    SELECT DISTINCT
                        CAST(LOCATION_CODE AS VARCHAR) AS locationcode,
                        CAST(MONTH AS VARCHAR) AS month_key,
                        CAST(SUSPECT_NAME AS VARCHAR) AS classification
                    FROM fact_anev
                    WHERE
                        LOCATION_CODE IS NOT NULL
                        AND MONTH IS NOT NULL
                        AND CAST(MONTH AS VARCHAR) <= ?
                        AND SUSPECT_NAME IS NOT NULL
                ),
                location_frequency AS (
                    SELECT
                        locationcode,
                        COUNT(DISTINCT month_key) AS months_seen
                    FROM location_month_classification
                    GROUP BY locationcode
                ),
                classification_locations AS (
                    SELECT DISTINCT
                        lmc.locationcode,
                        lmc.classification,
                        lf.months_seen
                    FROM location_month_classification lmc
                    INNER JOIN location_frequency lf
                        ON lmc.locationcode = lf.locationcode
                )
                SELECT
                    classification,
                    COUNT(*) AS total_customers,
                    COUNT(
                        CASE
                            WHEN months_seen > 1 THEN 1
                        END
                    ) AS repeat_customers,
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
                FROM classification_locations
                GROUP BY classification
                ORDER BY
                    repeat_customers DESC,
                    total_customers DESC
            """

            by_suspect_rows = conn.execute(
                by_suspect_sql,
                [str(month_key)],
            ).fetchall()

            by_suspect = [
                {
                    "classification": row[0],
                    "total_customers": int(row[1] or 0),
                    "repeat_customers": int(row[2] or 0),
                    "repeat_occurrences": int(row[3] or 0),
                }
                for row in by_suspect_rows
            ]

            return {
                "total_customers": total_customers,
                "repeat_customers": repeat_customers,
                "repeat_occurrences": repeat_occurrences,
                "repeat_rate_pct": repeat_rate_pct,
                "frequency": frequency,
                "by_suspect": by_suspect,
            }

        finally:
            conn.close()


    # ==========================================================
    # MAP POINTS / LOCATION COORDINATES
    # ==========================================================
    #
    # Suspect location -> IDPEL -> fact_customer_location
    #
    # Coordinate normalization:
    #   normal   : X = latitude,  Y = longitude
    #   reversed : X = longitude, Y = latitude
    #
    # One LOCATION_CODE is rendered as one point.
    # Raw measurement rows must never create duplicate markers.
    #
    # The map follows the same filters as the Suspect page:
    #   - month
    #   - UNITAP
    #   - suspect classification
    #   - repeat count
    #
    # Repeat count means distinct months in fact_anev up to the
    # selected month, exactly like get_repeat_summary().
    # ==========================================================

    def get_map_points(
        self,
        month_key: str,
        search: str | None = None,
        unitupi: str | None = None,
        unitap: str | None = None,
        unitup: str | None = None,
        tariff: str | None = None,
        suspect_name: str | None = None,
        repeat_count: int | None = None,
        inspection_status: str | None = None,
        limit: int = 100_000,
    ) -> dict[str, Any]:

        empty = {
            "total_locations": 0,
            "matched_idpel": 0,
            "mapped_locations": 0,
            "unmapped_locations": 0,
            "points": [],
        }

        if not dataset_exists("fact_anev"):
            return empty

        if not (
            dataset_exists("fact_customer_location")
            or dataset_exists("fact_pengecekan")
        ):
            return empty

        conn = get_connection()

        try:
            safe_limit = max(1, min(int(limit), 100_000))

            month_date = (
                f"{str(month_key)[:4]}-"
                f"{str(month_key)[4:6]}-01"
            )

            customer_location_source = (
                "fact_customer_location"
                if dataset_exists("fact_customer_location")
                else """(
                    SELECT
                        CAST(NULL AS VARCHAR) AS IDPEL,
                        CAST(NULL AS DOUBLE) AS KOORDINAT_X,
                        CAST(NULL AS DOUBLE) AS KOORDINAT_Y
                    WHERE FALSE
                )"""
            )

            pengecekan_source = (
                "fact_pengecekan"
                if dataset_exists("fact_pengecekan")
                else """(
                    SELECT
                        CAST(NULL AS VARCHAR) AS IDPEL,
                        CAST(NULL AS DOUBLE) AS LATITUDE,
                        CAST(NULL AS DOUBLE) AS LONGITUDE,
                        CAST(NULL AS TIMESTAMP) AS WAKTU_PERIKSA,
                        CAST(NULL AS VARCHAR) AS NAMA_PETUGAS,
                        CAST(NULL AS VARCHAR) AS CATATAN,
                        CAST(NULL AS VARCHAR) AS TINDAKLANJUT_PEMERIKSAAN
                    WHERE FALSE
                )"""
            )

            normalized_suspect_sql = """
                CASE
                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'ASYMMETRICPOWERBYINSTANT'
                    THEN 'ASYMMETRIC POWER BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'INCORRECTPHASEBYINSTANT'
                    THEN 'INCORRECT PHASE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'OVERCURRENTBYINSTANT'
                    THEN 'OVER CURRENT BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'OVERVOLTAGEBYINSTANT'
                    THEN 'OVER VOLTAGE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'REVERSALBYINSTANT'
                    THEN 'REVERSAL BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'TIMEDIFFERENCE-INSTANT'
                    THEN 'TIME DIFFERENCE - INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'UNBALANCECURRENTBYINSTANT'
                    THEN 'UNBALANCE CURRENT BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'UNDERVOLTAGEBYINSTANT'
                    THEN 'UNDER VOLTAGE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'VOLTAGEDIP-INSTANT'
                    THEN 'VOLTAGE DIP - INSTANT'

                    ELSE REGEXP_REPLACE(
                        TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                        '\\s+', ' ', 'g'
                    )
                END
            """

            clauses = [
                "CAST(MONTH AS VARCHAR) = ?",
                "LOCATION_CODE IS NOT NULL",
                "SUSPECT_NAME IS NOT NULL",
            ]

            params: list[Any] = [str(month_key)]

            if unitupi:
                clauses.append("CAST(UNITUPI AS VARCHAR) = ?")
                params.append(str(unitupi))

            if unitap:
                clauses.append("CAST(UNITAP AS VARCHAR) = ?")
                params.append(str(unitap))

            if unitup:
                clauses.append("CAST(UNITUP AS VARCHAR) = ?")
                params.append(str(unitup))

            if tariff:
                clauses.append("CAST(TARIFF AS VARCHAR) = ?")
                params.append(str(tariff))

            if suspect_name:
                clauses.append(f"{normalized_suspect_sql} = ?")
                params.append(
                    " ".join(str(suspect_name).strip().upper().split())
                )

            if search:
                search_value = f"%{search.strip()}%"
                clauses.append(
                    "(CAST(LOCATION_CODE AS VARCHAR) ILIKE ? "
                    "OR CAST(LOCATION_NAME AS VARCHAR) ILIKE ?)"
                )
                params.extend([search_value, search_value])

            inspection_filter = None
            if inspection_status:
                inspection_filter = str(inspection_status).strip().upper()

            repeat_cte = ""
            repeat_join = ""
            repeat_params: list[Any] = []

            if repeat_count is not None:
                repeat_cte = """
                    , repeat_frequency AS (
                        SELECT
                            CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE,
                            COUNT(DISTINCT CAST(MONTH AS VARCHAR)) AS REPEAT_COUNT
                        FROM fact_anev
                        WHERE LOCATION_CODE IS NOT NULL
                          AND MONTH IS NOT NULL
                          AND CAST(MONTH AS VARCHAR) <= ?
                        GROUP BY LOCATION_CODE
                    )
                """

                repeat_join = """
                    INNER JOIN repeat_frequency rf
                        ON rf.LOCATION_CODE = s.LOCATION_CODE
                       AND rf.REPEAT_COUNT = ?
                """

                repeat_params = [
                    str(month_key),
                    int(repeat_count),
                ]

            sql = f"""
                WITH suspect_rows AS (
                    SELECT
                        CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE,
                        CAST(LOCATION_CODE AS VARCHAR) AS IDPEL,
                        CAST(LOCATION_NAME AS VARCHAR) AS LOCATION_NAME,
                        CAST(UNITUPI AS VARCHAR) AS UNITUPI,
                        CAST(UNITAP AS VARCHAR) AS UNITAP,
                        CAST(UNITUP AS VARCHAR) AS UNITUP,
                        CAST(TARIFF AS VARCHAR) AS TARIFF,
                        TRY_CAST(POWER AS DOUBLE) AS POWER,
                        {normalized_suspect_sql} AS SUSPECT_NAME
                    FROM fact_anev
                    WHERE {' AND '.join(clauses)}
                ),

                suspect_locations AS (
                    SELECT
                        LOCATION_CODE,
                        ANY_VALUE(IDPEL) AS IDPEL,
                        ANY_VALUE(LOCATION_NAME) AS LOCATION_NAME,
                        ANY_VALUE(UNITUPI) AS UNITUPI,
                        ANY_VALUE(UNITAP) AS UNITAP,
                        ANY_VALUE(UNITUP) AS UNITUP,
                        ANY_VALUE(TARIFF) AS TARIFF,
                        ANY_VALUE(POWER) AS POWER,
                        STRING_AGG(
                            DISTINCT SUSPECT_NAME,
                            ', ' ORDER BY SUSPECT_NAME
                        ) AS SUSPECT_NAME
                    FROM suspect_rows
                    GROUP BY LOCATION_CODE
                )

                {repeat_cte}

                , customer_location_raw AS (
                    SELECT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL,
                        TRY_CAST(KOORDINAT_X AS DOUBLE) AS RAW_X,
                        TRY_CAST(KOORDINAT_Y AS DOUBLE) AS RAW_Y
                    FROM {customer_location_source}
                    WHERE IDPEL IS NOT NULL
                ),

                customer_location_normalized AS (
                    SELECT
                        IDPEL,

                        CASE
                            WHEN RAW_X BETWEEN -6.6 AND -3.7
                             AND RAW_Y BETWEEN 103.0 AND 106.5
                            THEN RAW_X

                            WHEN RAW_X BETWEEN 103.0 AND 106.5
                             AND RAW_Y BETWEEN -6.6 AND -3.7
                            THEN RAW_Y

                            ELSE NULL
                        END AS LATITUDE,

                        CASE
                            WHEN RAW_X BETWEEN -6.6 AND -3.7
                             AND RAW_Y BETWEEN 103.0 AND 106.5
                            THEN RAW_Y

                            WHEN RAW_X BETWEEN 103.0 AND 106.5
                             AND RAW_Y BETWEEN -6.6 AND -3.7
                            THEN RAW_X

                            ELSE NULL
                        END AS LONGITUDE

                    FROM customer_location_raw
                ),

                customer_location_by_idpel AS (
                    SELECT
                        IDPEL,
                        LATITUDE,
                        LONGITUDE
                    FROM (
                        SELECT
                            IDPEL,
                            LATITUDE,
                            LONGITUDE,
                            ROW_NUMBER() OVER (
                                PARTITION BY IDPEL
                                ORDER BY
                                    CASE
                                        WHEN LATITUDE IS NOT NULL
                                         AND LONGITUDE IS NOT NULL
                                        THEN 0
                                        ELSE 1
                                    END
                            ) AS RN
                        FROM customer_location_normalized
                        WHERE LATITUDE IS NOT NULL
                          AND LONGITUDE IS NOT NULL
                    ) x
                    WHERE RN = 1
                ),

                pengecekan_raw AS (
                    SELECT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL,

                        TRY_CAST(LATITUDE AS DOUBLE) AS LATITUDE,
                        TRY_CAST(LONGITUDE AS DOUBLE) AS LONGITUDE,

                        WAKTU_PERIKSA,
                        CAST(NAMA_PETUGAS AS VARCHAR) AS NAMA_PETUGAS,
                        CAST(CATATAN AS VARCHAR) AS CATATAN,
                        CAST(
                            TINDAKLANJUT_PEMERIKSAAN
                            AS VARCHAR
                        ) AS TINDAKLANJUT_PEMERIKSAAN

                    FROM {pengecekan_source}

                    WHERE IDPEL IS NOT NULL
                ),

                pengecekan_by_idpel AS (
                    SELECT
                        IDPEL,
                        LATITUDE,
                        LONGITUDE
                    FROM (
                        SELECT
                            IDPEL,
                            LATITUDE,
                            LONGITUDE,
                            ROW_NUMBER() OVER (
                                PARTITION BY REGEXP_REPLACE(TRIM(CAST(IDPEL AS VARCHAR)), '\\.0$', '')
                                ORDER BY WAKTU_PERIKSA DESC NULLS LAST
                            ) AS RN
                        FROM pengecekan_raw
                        WHERE LATITUDE BETWEEN -6.6 AND -3.7
                          AND LONGITUDE BETWEEN 103.0 AND 106.5
                    ) x
                    WHERE RN = 1
                ),

                inspection_by_idpel AS (
                    SELECT
                        IDPEL,
                        WAKTU_PERIKSA,
                        NAMA_PETUGAS,
                        CATATAN,
                        TINDAKLANJUT_PEMERIKSAAN
                    FROM (
                        SELECT
                            REGEXP_REPLACE(TRIM(CAST(IDPEL AS VARCHAR)), '\\.0$', '') AS IDPEL,
                            WAKTU_PERIKSA,
                            NAMA_PETUGAS,
                            CATATAN,
                            TINDAKLANJUT_PEMERIKSAAN,

                            ROW_NUMBER() OVER (
                                PARTITION BY REGEXP_REPLACE(
                                    TRIM(CAST(IDPEL AS VARCHAR)),
                                    '\\.0$',
                                    ''
                                )
                                ORDER BY WAKTU_PERIKSA DESC NULLS LAST
                            ) AS RN

                        FROM fact_pengecekan

                        WHERE IDPEL IS NOT NULL

                          AND WAKTU_PERIKSA >=
                              TRY_CAST(? AS DATE)

                          AND WAKTU_PERIKSA <
                              DATE_ADD(
                                  TRY_CAST(? AS DATE),
                                  INTERVAL 1 MONTH
                              )

                          AND WAKTU_PERIKSA IS NOT NULL
                    ) x

                    WHERE RN = 1
                ),

                mapped AS (
                    SELECT
                        s.LOCATION_CODE,
                        s.IDPEL,
                        s.LOCATION_NAME,
                        s.UNITUPI,
                        s.UNITAP,
                        s.UNITUP,
                        s.TARIFF,
                        s.POWER,
                        s.SUSPECT_NAME,

                        CASE
                            WHEN c.LATITUDE IS NOT NULL
                             AND c.LONGITUDE IS NOT NULL
                            THEN c.LATITUDE
                            ELSE p.LATITUDE
                        END AS LATITUDE,

                        CASE
                            WHEN c.LATITUDE IS NOT NULL
                             AND c.LONGITUDE IS NOT NULL
                            THEN c.LONGITUDE
                            ELSE p.LONGITUDE
                        END AS LONGITUDE,

                        CASE
                            WHEN c.LATITUDE IS NOT NULL
                             AND c.LONGITUDE IS NOT NULL
                            THEN 'customer_location'

                            WHEN p.LATITUDE IS NOT NULL
                             AND p.LONGITUDE IS NOT NULL
                            THEN 'pengecekan'

                            ELSE NULL
                        END AS COORDINATE_SOURCE,

                        CASE
                            WHEN i.IDPEL IS NOT NULL
                            THEN 'SUDAH_PERIKSA'
                            ELSE 'BELUM_PERIKSA'
                        END AS INSPECTION_STATUS,

                        i.WAKTU_PERIKSA,
                        i.NAMA_PETUGAS,
                        i.CATATAN,
                        i.TINDAKLANJUT_PEMERIKSAAN

                    FROM suspect_locations s

                    LEFT JOIN customer_location_by_idpel c
                        ON REGEXP_REPLACE(
                            TRIM(s.IDPEL),
                            '\\.0$',
                            ''
                        ) = c.IDPEL

                    LEFT JOIN pengecekan_by_idpel p
                        ON REGEXP_REPLACE(
                            TRIM(s.IDPEL),
                            '\\.0$',
                            ''
                        ) = p.IDPEL

                    LEFT JOIN inspection_by_idpel i
                        ON REGEXP_REPLACE(
                            TRIM(CAST(s.LOCATION_CODE AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) = REGEXP_REPLACE(
                            TRIM(CAST(i.IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        )

                    {repeat_join}
                )

                SELECT
                    LOCATION_CODE,
                    IDPEL,
                    LOCATION_NAME,
                    UNITUPI,
                    UNITAP,
                    UNITUP,
                    TARIFF,
                    POWER,
                    SUSPECT_NAME,
                    LATITUDE,
                    LONGITUDE,
                    COORDINATE_SOURCE,
                    INSPECTION_STATUS,
                    WAKTU_PERIKSA,
                    NAMA_PETUGAS,
                    CATATAN,
                    TINDAKLANJUT_PEMERIKSAAN

                FROM mapped
                WHERE (
                    ? IS NULL
                    OR INSPECTION_STATUS = ?
                )

                ORDER BY UNITUP, LOCATION_CODE

                LIMIT ?
            """

            query_params = [
                *params,
                *repeat_params,
                month_date,
                month_date,
                inspection_filter,
                inspection_filter,
                safe_limit,
            ]

            rows = conn.execute(
                sql,
                query_params,
            ).fetchall()

            points = []

            for row in rows:
                latitude = row[9]
                longitude = row[10]

                # Jangan buang hasil inspeksi hanya karena koordinat kosong.
                # Status inspeksi (SUDAH_PERIKSA/BELUM_PERIKSA) harus tetap
                # dikembalikan untuk kebutuhan filter dashboard.
                points.append({
                    "location_code": str(row[0]),
                    "idpel": str(row[1]) if row[1] is not None else None,
                    "location_name": row[2],
                    "unitupi": row[3],
                    "unitap": row[4],
                    "unitup": row[5],
                    "tariff": row[6],
                    "power": row[7],
                    "suspect_name": row[8],

                    "latitude": float(latitude) if latitude is not None else None,
                    "longitude": float(longitude) if longitude is not None else None,

                    "coordinate_source": row[11],

                    "inspection_status": row[12],

                    "waktu_periksa": (
                        row[13].isoformat()
                        if row[13] is not None
                        else None
                    ),

                    "nama_petugas": row[14],
                    "catatan": row[15],
                    "tindaklanjut_pemeriksaan": row[16],
                })

            # Coverage tetap dihitung berdasarkan populasi lokasi,
            # bukan berdasarkan LIMIT.
            coverage_sql = f"""
                WITH suspect_locations AS (
                    SELECT
                        CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE
                    FROM fact_anev
                    WHERE {' AND '.join(clauses)}
                    GROUP BY LOCATION_CODE
                ),

                customer_location_raw AS (
                    SELECT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL,

                        TRY_CAST(KOORDINAT_X AS DOUBLE) AS RAW_X,
                        TRY_CAST(KOORDINAT_Y AS DOUBLE) AS RAW_Y

                    FROM {customer_location_source}

                    WHERE IDPEL IS NOT NULL
                ),

                customer_location_by_idpel AS (
                    SELECT DISTINCT
                        IDPEL

                    FROM customer_location_raw

                    WHERE (
                        RAW_X BETWEEN -6.6 AND -3.7
                        AND RAW_Y BETWEEN 103.0 AND 106.5
                    )

                    OR (
                        RAW_X BETWEEN 103.0 AND 106.5
                        AND RAW_Y BETWEEN -6.6 AND -3.7
                    )
                ),

                pengecekan_by_idpel AS (
                    SELECT DISTINCT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL

                    FROM {pengecekan_source}

                    WHERE IDPEL IS NOT NULL
                      AND LATITUDE BETWEEN -6.6 AND -3.7
                      AND LONGITUDE BETWEEN 103.0 AND 106.5
                )

                SELECT
                    COUNT(DISTINCT s.LOCATION_CODE),

                    COUNT(
                        DISTINCT CASE
                            WHEN c.IDPEL IS NOT NULL
                              OR p.IDPEL IS NOT NULL
                            THEN s.LOCATION_CODE
                        END
                    ),

                    COUNT(DISTINCT s.LOCATION_CODE)

                FROM suspect_locations s

                LEFT JOIN customer_location_by_idpel c
                    ON REGEXP_REPLACE(
                        TRIM(s.LOCATION_CODE),
                        '\\.0$',
                        ''
                    ) = c.IDPEL

                LEFT JOIN pengecekan_by_idpel p
                    ON REGEXP_REPLACE(
                        TRIM(s.LOCATION_CODE),
                        '\\.0$',
                        ''
                    ) = p.IDPEL
            """

            coverage = conn.execute(
                coverage_sql,
                params,
            ).fetchone()

            total_locations = int(
                coverage[0] or 0
            ) if coverage else 0

            mapped_locations = int(
                coverage[1] or 0
            ) if coverage else 0

            matched_idpel = int(
                coverage[2] or 0
            ) if coverage else 0

            return {
                "total_locations": total_locations,
                "matched_idpel": matched_idpel,
                "mapped_locations": mapped_locations,
                "unmapped_locations": max(
                    total_locations - mapped_locations,
                    0,
                ),
                "points": points,
            }

        finally:
            conn.close()
