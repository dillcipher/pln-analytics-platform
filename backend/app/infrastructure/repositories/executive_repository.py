from __future__ import annotations

import logging
import re
from typing import Any

from app.database.warehouse import Warehouse

logger = logging.getLogger(__name__)


class ExecutiveRepository:
    """
    Repository for Executive analytical views.

    Design principles:
    - month is an explicit filter whenever supplied;
    - PRA and PASCA are read from their own DLPD facts;
    - ANEV is treated as the inspection/finding layer;
    - repeat means the same location exists in multiple months, not
      multiple rows in one month;
    - classification labels are normalized before comparison;
    - statistical outputs are descriptive/model-based only when the
      underlying numeric variables actually exist.
    """

    # ==========================================================
    # CONNECTION
    # ==========================================================

    @staticmethod
    def execute_one(query: str):
        conn = Warehouse.connect()
        try:
            return conn.execute(query).fetchone()
        finally:
            conn.close()

    @staticmethod
    def execute_all(query: str):
        conn = Warehouse.connect()
        try:
            return conn.execute(query).fetchall()
        finally:
            conn.close()

    @staticmethod
    def execute_dicts(query: str) -> list[dict[str, Any]]:
        conn = Warehouse.connect()
        try:
            cursor = conn.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    # ==========================================================
    # SCHEMA
    # ==========================================================

    @classmethod
    def _table_exists(cls, table_name: str) -> bool:
        row = cls.execute_one(
            f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower('{table_name}')
            """
        )
        return bool(row and row[0])

    @classmethod
    def _columns(cls, table_name: str) -> list[str]:
        if not cls._table_exists(table_name):
            return []

        rows = cls.execute_all(
            f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE lower(table_name) = lower('{table_name}')
            ORDER BY ordinal_position
            """
        )
        return [str(row[0]) for row in rows]

    @classmethod
    def _column_map(cls, table_name: str) -> dict[str, str]:
        return {column.lower(): column for column in cls._columns(table_name)}

    @classmethod
    def _find_column(
        cls,
        table_name: str,
        candidates: list[str],
    ) -> str | None:
        mapping = cls._column_map(table_name)
        for candidate in candidates:
            actual = mapping.get(candidate.lower())
            if actual:
                return actual
        return None

    @classmethod
    def _find_numeric_columns(cls, table_name: str) -> list[str]:
        if not cls._table_exists(table_name):
            return []

        rows = cls.execute_all(
            f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE lower(table_name) = lower('{table_name}')
            ORDER BY ordinal_position
            """
        )

        numeric_types = {
            "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
            "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT",
            "FLOAT", "DOUBLE", "DECIMAL",
        }

        return [
            str(column)
            for column, data_type in rows
            if any(str(data_type).upper().startswith(t) for t in numeric_types)
        ]

    @classmethod
    def _month_column(cls, table_name: str) -> str | None:
        return cls._find_column(
            table_name,
            ["MONTH_KEY", "MONTH", "BUSINESS_MONTH", "PERIOD", "PERIODE"],
        )

    @classmethod
    def _classification_column(cls, table_name: str) -> str | None:
        return cls._find_column(
            table_name,
            [
                "CLASSIFICATION",
                "KLASIFIKASI",
                "KLASIFIKASI_SUSPECT",
                "SUSPECT_CLASSIFICATION",
                "CATEGORY",
                "KATEGORI",
            ],
        )

    @classmethod
    def _location_column(cls, table_name: str) -> str | None:
        return cls._find_column(
            table_name,
            [
                "LOCATION_CODE",
                "LOCATION",
                "LOC_CODE",
                "ID_LOCATION",
                "IDPEL",
                "CUSTOMER_ID",
            ],
        )

    @classmethod
    def _unitup_column(cls, table_name: str) -> str | None:
        return cls._find_column(
            table_name,
            ["UNITUP", "UNIT_UP", "UNIT", "ULP"],
        )

    @classmethod
    def _unitap_column(cls, table_name: str) -> str | None:
        return cls._find_column(
            table_name,
            ["UNITAP", "UNIT_AP"],
        )

    @classmethod
    def _tariff_column(cls, table_name: str) -> str | None:
        return cls._find_column(
            table_name,
            ["TARIFF", "TARIF", "TARIF_CODE"],
        )

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def normalize_classification(value: Any) -> str:
        text = " ".join(str(value or "").strip().upper().split())
        replacements = {
            "ASYMMETRICPOWER": "ASYMMETRIC POWER",
            "INCORRECTPHASE": "INCORRECT PHASE",
            "OVERCURRENT": "OVER CURRENT",
            "REVERSAL BYINSTANT": "REVERSAL BY INSTANT",
            "VOLTAGE DIP- INSTANT": "VOLTAGE DIP - INSTANT",
            "VOLTAGE DIP-INSTANT": "VOLTAGE DIP - INSTANT",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        return text

    @classmethod
    def _classification_sql(cls, column: str) -> str:
        # Normalize common source inconsistencies directly in DuckDB.
        expression = f"""
            UPPER(TRIM(CAST("{column}" AS VARCHAR)))
        """
        replacements = [
            ("ASYMMETRICPOWER", "ASYMMETRIC POWER"),
            ("INCORRECTPHASE", "INCORRECT PHASE"),
            ("OVERCURRENT", "OVER CURRENT"),
            ("REVERSAL BYINSTANT", "REVERSAL BY INSTANT"),
            ("VOLTAGE DIP- INSTANT", "VOLTAGE DIP - INSTANT"),
            ("VOLTAGE DIP-INSTANT", "VOLTAGE DIP - INSTANT"),
        ]
        for source, target in replacements:
            expression = (
                f"REPLACE({expression}, "
                f"'{source}', '{target}')"
            )
        return expression

    @staticmethod
    def _month_filter(column: str, month_key: str | None) -> str:
        if not month_key:
            return ""
        safe = str(month_key).replace("'", "''")
        return f"""
            AND CAST("{column}" AS VARCHAR) = '{safe}'
        """

    # ==========================================================
    # KPI
    # ==========================================================

    @classmethod
    def get_kpis(cls, month_key: str | None = None) -> dict[str, Any]:
        """
        Executive KPI is based on the selected month.

        - total_customers: unique DLPD customer/location population when
          available, otherwise unique ANEV locations.
        - total_suspects: unique ANEV locations with a classification.
        - total_normal: DLPD population minus suspect population, bounded at 0.
        - total_findings: unique finding rows/events when a finding/status
          field exists; otherwise 0 rather than pretending every ANEV row
          is a finding.
        """

        anev_exists = cls._table_exists("fact_anev")
        pra_exists = cls._table_exists("fact_dlpd_prabayar")
        pasca_exists = cls._table_exists("fact_dlpd_pascabayar")

        anev_loc = cls._location_column("fact_anev") if anev_exists else None
        anev_month = cls._month_column("fact_anev") if anev_exists else None
        classification = (
            cls._classification_column("fact_anev")
            if anev_exists else None
        )

        total_customers = 0

        # Prefer DLPD population because the Executive dashboard is
        # about the inspection population, not only ANEV events.
        for table in ("fact_dlpd_prabayar", "fact_dlpd_pascabayar"):
            if not cls._table_exists(table):
                continue

            location = cls._location_column(table)
            month = cls._month_column(table)

            if location:
                month_filter = cls._month_filter(month, month_key) if month else ""
                try:
                    row = cls.execute_one(
                        f"""
                        SELECT COUNT(DISTINCT "{location}")
                        FROM {table}
                        WHERE "{location}" IS NOT NULL
                        {month_filter}
                        """
                    )
                    total_customers += int(row[0] or 0) if row else 0
                except Exception:
                    logger.exception("Failed DLPD population KPI: %s", table)

        if total_customers == 0 and anev_loc:
            month_filter = cls._month_filter(anev_month, month_key) if anev_month else ""
            row = cls.execute_one(
                f"""
                SELECT COUNT(DISTINCT "{anev_loc}")
                FROM fact_anev
                WHERE "{anev_loc}" IS NOT NULL
                {month_filter}
                """
            )
            total_customers = int(row[0] or 0) if row else 0

        total_suspects = 0
        if anev_exists and anev_loc and classification:
            month_filter = cls._month_filter(anev_month, month_key) if anev_month else ""
            row = cls.execute_one(
                f"""
                SELECT COUNT(DISTINCT "{anev_loc}")
                FROM fact_anev
                WHERE "{anev_loc}" IS NOT NULL
                  AND "{classification}" IS NOT NULL
                  AND TRIM(CAST("{classification}" AS VARCHAR)) <> ''
                {month_filter}
                """
            )
            total_suspects = int(row[0] or 0) if row else 0

        total_normal = max(total_customers - total_suspects, 0)

        total_findings = 0
        if anev_exists:
            finding_col = cls._find_column(
                "fact_anev",
                ["FINDING", "FINDINGS", "TEMUAN", "TOTAL_FINDINGS", "HAS_FINDING"],
            )
            if finding_col and anev_loc:
                month_filter = cls._month_filter(anev_month, month_key) if anev_month else ""
                row = cls.execute_one(
                    f"""
                    SELECT COUNT(DISTINCT "{anev_loc}")
                    FROM fact_anev
                    WHERE "{anev_loc}" IS NOT NULL
                      AND TRY_CAST("{finding_col}" AS DOUBLE) > 0
                    {month_filter}
                    """
                )
                total_findings = int(row[0] or 0) if row else 0

        # Coverage is measured against the selected population.
        progress_pct = (
            total_suspects / total_customers * 100
            if total_customers
            else 0.0
        )

        hit_rate_pct = (
            total_findings / total_suspects * 100
            if total_suspects
            else 0.0
        )

        return {
            "month_key": month_key,
            "total_customers": total_customers,
            "total_suspects": total_suspects,
            "total_normal": total_normal,
            "total_findings": total_findings,
            "remaining_inspection": total_normal,
            "progress_pct": round(progress_pct, 2),
            "hit_rate_pct": round(hit_rate_pct, 2),
        }

    # ==========================================================
    # MONTHS
    # ==========================================================

    @classmethod
    def get_months(cls) -> list[str]:
        if not cls._table_exists("fact_anev"):
            return []

        month = cls._month_column("fact_anev")
        if month:
            rows = cls.execute_all(
                f"""
                SELECT DISTINCT CAST("{month}" AS VARCHAR)
                FROM fact_anev
                WHERE "{month}" IS NOT NULL
                ORDER BY 1
                """
            )
            direct = [str(row[0]) for row in rows if row[0] is not None]
            if direct and all(re.fullmatch(r"20\d{4}", x) for x in direct):
                return direct

        source_column = cls._find_column(
            "fact_anev",
            ["SOURCE_FILE", "source_file", "FILE_NAME", "filename"],
        )
        if not source_column:
            return []

        rows = cls.execute_all(
            f"""
            SELECT DISTINCT "{source_column}"
            FROM fact_anev
            """
        )

        months: set[str] = set()
        for (filename,) in rows:
            if not filename:
                continue
            value = str(filename)
            match = re.search(r"(20\d{2})[-_/]?(0[1-9]|1[0-2])", value)
            if match:
                months.add(f"{match.group(1)}{match.group(2)}")
                continue
            match = re.search(r"20\d{4}", value)
            if match:
                months.add(match.group())
        return sorted(months)

    # ==========================================================
    # BASIC DISTRIBUTIONS
    # ==========================================================

    @classmethod
    def get_unit_chart(cls, month_key: str | None = None):
        table = "fact_anev"
        column = cls._unitap_column(table)
        month = cls._month_column(table)
        if not column:
            return []

        month_filter = cls._month_filter(month, month_key) if month else ""
        return cls.execute_all(
            f"""
            SELECT "{column}" AS LABEL, COUNT(DISTINCT
                COALESCE(CAST("{cls._location_column(table) or column}" AS VARCHAR),
                         CAST(ROW_NUMBER() OVER () AS VARCHAR))
            ) AS TOTAL
            FROM {table}
            WHERE "{column}" IS NOT NULL
            {month_filter}
            GROUP BY "{column}"
            ORDER BY TOTAL DESC
            """
        )

    @classmethod
    def get_tariff_chart(cls, month_key: str | None = None):
        table = "fact_anev"
        column = cls._tariff_column(table)
        month = cls._month_column(table)
        if not column:
            return []

        month_filter = cls._month_filter(month, month_key) if month else ""
        return cls.execute_all(
            f"""
            SELECT "{column}" AS LABEL, COUNT(*) AS TOTAL
            FROM {table}
            WHERE "{column}" IS NOT NULL
            {month_filter}
            GROUP BY "{column}"
            ORDER BY TOTAL DESC
            """
        )

    @classmethod
    def get_suspect_classification(cls, month_key: str | None = None):
        table = "fact_anev"
        classification = cls._classification_column(table)
        month = cls._month_column(table)
        if not classification:
            return []

        expression = cls._classification_sql(classification)
        month_filter = cls._month_filter(month, month_key) if month else ""

        return cls.execute_all(
            f"""
            SELECT {expression} AS LABEL, COUNT(*) AS TOTAL
            FROM {table}
            WHERE "{classification}" IS NOT NULL
              AND TRIM(CAST("{classification}" AS VARCHAR)) <> ''
              {month_filter}
            GROUP BY 1
            ORDER BY TOTAL DESC
            """
        )

    # ==========================================================
    # PRA / PASCA
    # ==========================================================

    @classmethod
    def _customer_type_classification(
        cls,
        table: str,
        customer_type: str,
        month_key: str | None = None,
    ) -> list[tuple]:
        if not cls._table_exists(table):
            return []

        classification = cls._classification_column(table)
        month = cls._month_column(table)
        if not classification:
            return []

        expression = cls._classification_sql(classification)
        month_filter = cls._month_filter(month, month_key) if month else ""

        return cls.execute_all(
            f"""
            SELECT
                '{customer_type}' AS CUSTOMER_TYPE,
                {expression} AS CLASSIFICATION,
                COUNT(DISTINCT COALESCE(
                    CAST("{cls._location_column(table) or classification}" AS VARCHAR),
                    CAST(ROW_NUMBER() OVER () AS VARCHAR)
                )) AS TOTAL
            FROM {table}
            WHERE "{classification}" IS NOT NULL
              AND TRIM(CAST("{classification}" AS VARCHAR)) <> ''
              {month_filter}
            GROUP BY 1, 2
            ORDER BY TOTAL DESC
            """
        )

    @classmethod
    def get_pra_pasca_suspect(cls, month_key: str | None = None):
        """
        PRA and PASCA are explicitly sourced from their own facts.

        This is intentionally NOT derived from fact_anev, because doing so
        makes the two populations identical.
        """
        results = []
        results.extend(
            cls._customer_type_classification(
                "fact_dlpd_prabayar", "PRA", month_key
            )
        )
        results.extend(
            cls._customer_type_classification(
                "fact_dlpd_pascabayar", "PASCA", month_key
            )
        )
        return results

    @classmethod
    def get_customer_type_summary(cls, month_key: str | None = None):
        result = []
        for customer_type, table in [
            ("PRA", "fact_dlpd_prabayar"),
            ("PASCA", "fact_dlpd_pascabayar"),
        ]:
            if not cls._table_exists(table):
                continue

            location = cls._location_column(table)
            month = cls._month_column(table)
            if not location:
                continue

            month_filter = cls._month_filter(month, month_key) if month else ""
            row = cls.execute_one(
                f"""
                SELECT COUNT(DISTINCT "{location}")
                FROM {table}
                WHERE "{location}" IS NOT NULL
                {month_filter}
                """
            )
            result.append(
                (
                    customer_type,
                    int(row[0] or 0) if row else 0,
                )
            )
        return result

    @classmethod
    def get_pra_monthly(cls, month_key: str | None = None) -> dict[str, Any]:
        classifications = cls.get_pra_pasca_suspect(month_key)
        pra = [
            row for row in classifications
            if str(row[0]).upper() == "PRA"
        ]

        table = "fact_dlpd_prabayar"
        locations = 0
        unitap_rows: list[tuple] = []

        if cls._table_exists(table):
            location = cls._location_column(table)
            unitap = cls._unitap_column(table)
            month = cls._month_column(table)

            if location:
                month_filter = cls._month_filter(month, month_key) if month else ""
                row = cls.execute_one(
                    f"""
                    SELECT COUNT(DISTINCT "{location}")
                    FROM {table}
                    WHERE "{location}" IS NOT NULL
                    {month_filter}
                    """
                )
                locations = int(row[0] or 0) if row else 0

            if unitap:
                month_filter = cls._month_filter(month, month_key) if month else ""
                unitap_rows = cls.execute_all(
                    f"""
                    SELECT "{unitap}" AS UNITAP,
                           COUNT(DISTINCT "{location or unitap}") AS TOTAL
                    FROM {table}
                    WHERE "{unitap}" IS NOT NULL
                    {month_filter}
                    GROUP BY "{unitap}"
                    ORDER BY TOTAL DESC
                    """
                )

        return {
            "total_locations": locations,
            "total_classifications": len(pra),
            "classification": [
                {
                    "classification": row[1],
                    "total": int(row[2] or 0),
                }
                for row in pra
            ],
            "unitap": [
                {
                    "unitap": str(row[0]),
                    "total": int(row[1] or 0),
                }
                for row in unitap_rows
            ],
        }

    # ==========================================================
    # PASCA REPEAT / PERSISTENCE
    # ==========================================================

    @classmethod
    def get_pasca_repeat(cls, month_key: str | None = None) -> dict[str, Any]:
        table = "fact_dlpd_pascabayar"
        if not cls._table_exists(table):
            return {
                "total_locations": 0,
                "repeat_locations": 0,
                "repeat_occurrences": 0,
                "repeat_rate_pct": 0.0,
                "frequency": [],
                "classification": [],
            }

        location = cls._location_column(table)
        month = cls._month_column(table)
        classification = cls._classification_column(table)

        if not location:
            return {
                "total_locations": 0,
                "repeat_locations": 0,
                "repeat_occurrences": 0,
                "repeat_rate_pct": 0.0,
                "frequency": [],
                "classification": [],
            }

        # A selected month is required for a meaningful persistence metric.
        if not month_key or not month:
            return {
                "total_locations": 0,
                "repeat_locations": 0,
                "repeat_occurrences": 0,
                "repeat_rate_pct": 0.0,
                "frequency": [],
                "classification": [],
            }

        safe_month = str(month_key).replace("'", "''")

        # Number of distinct months in which each location appeared.
        # Multiple rows in the same month do not create repeat.
        rows = cls.execute_all(
            f"""
            WITH location_month AS (
                SELECT DISTINCT
                    CAST("{location}" AS VARCHAR) AS LOCATION_CODE,
                    CAST("{month}" AS VARCHAR) AS MONTH_KEY
                FROM {table}
                WHERE "{location}" IS NOT NULL
                  AND "{month}" IS NOT NULL
            ),
            selected AS (
                SELECT LOCATION_CODE
                FROM location_month
                WHERE MONTH_KEY = '{safe_month}'
            ),
            history AS (
                SELECT
                    lm.LOCATION_CODE,
                    COUNT(DISTINCT lm.MONTH_KEY) AS MONTH_COUNT
                FROM location_month lm
                INNER JOIN selected s
                    ON s.LOCATION_CODE = lm.LOCATION_CODE
                WHERE lm.MONTH_KEY <= '{safe_month}'
                GROUP BY lm.LOCATION_CODE
            )
            SELECT MONTH_COUNT, COUNT(*) AS LOCATIONS
            FROM history
            GROUP BY MONTH_COUNT
            ORDER BY MONTH_COUNT
            """
        )

        total_locations = sum(int(row[1] or 0) for row in rows)
        repeat_locations = sum(
            int(row[1] or 0)
            for row in rows
            if int(row[0] or 0) > 1
        )

        # Repeat occurrences = additional historical months beyond the
        # selected month, not raw event rows.
        repeat_occurrences = sum(
            max(int(row[0] or 0) - 1, 0) * int(row[1] or 0)
            for row in rows
        )

        repeat_rate = (
            repeat_locations / total_locations * 100
            if total_locations
            else 0.0
        )

        classification_rows: list[tuple] = []

        if classification:
            expression = cls._classification_sql(classification)

            classification_rows = cls.execute_all(
                f"""
                WITH location_month_class AS (
                    SELECT DISTINCT
                        CAST("{location}" AS VARCHAR) AS LOCATION_CODE,
                        CAST("{month}" AS VARCHAR) AS MONTH_KEY,
                        {expression} AS CLASSIFICATION
                    FROM {table}
                    WHERE "{location}" IS NOT NULL
                      AND "{month}" IS NOT NULL
                      AND "{classification}" IS NOT NULL
                      AND TRIM(CAST("{classification}" AS VARCHAR)) <> ''
                ),
                selected AS (
                    SELECT DISTINCT LOCATION_CODE
                    FROM location_month_class
                    WHERE MONTH_KEY = '{safe_month}'
                ),
                history AS (
                    SELECT
                        LOCATION_CODE,
                        CLASSIFICATION,
                        COUNT(DISTINCT MONTH_KEY) AS MONTH_COUNT
                    FROM location_month_class
                    WHERE MONTH_KEY <= '{safe_month}'
                    GROUP BY LOCATION_CODE, CLASSIFICATION
                ),
                selected_class AS (
                    SELECT
                        h.LOCATION_CODE,
                        h.CLASSIFICATION,
                        h.MONTH_COUNT
                    FROM history h
                    INNER JOIN selected s
                        ON s.LOCATION_CODE = h.LOCATION_CODE
                    WHERE h.CLASSIFICATION IS NOT NULL
                )
                SELECT
                    CLASSIFICATION,
                    COUNT(DISTINCT LOCATION_CODE) AS TOTAL_LOCATIONS,
                    COUNT(DISTINCT CASE
                        WHEN MONTH_COUNT > 1 THEN LOCATION_CODE
                    END) AS REPEAT_LOCATIONS,
                    SUM(GREATEST(MONTH_COUNT - 1, 0)) AS REPEAT_OCCURRENCES
                FROM selected_class
                GROUP BY CLASSIFICATION
                ORDER BY TOTAL_LOCATIONS DESC
                """
            )

        frequency = [
            {
                "repeat_count": int(row[0] or 0),
                "locations": int(row[1] or 0),
            }
            for row in rows
        ]

        classification_result = [
            {
                "classification": str(row[0]),
                "total_locations": int(row[1] or 0),
                "repeat_locations": int(row[2] or 0),
                "repeat_occurrences": int(row[3] or 0),
            }
            for row in classification_rows
        ]

        return {
            "total_locations": total_locations,
            "repeat_locations": repeat_locations,
            "repeat_occurrences": repeat_occurrences,
            "repeat_rate_pct": round(repeat_rate, 2),
            "frequency": frequency,
            "classification": classification_result,
        }

    # ==========================================================
    # EDA: TREND
    # ==========================================================

    @classmethod
    def get_monthly_trend(cls, month_key: str | None = None):
        table = "fact_anev"
        month = cls._month_column(table)
        location = cls._location_column(table)
        if not month or not location:
            return []

        rows = cls.execute_all(
            f"""
            SELECT
                CAST("{month}" AS VARCHAR) AS LABEL,
                COUNT(DISTINCT "{location}") AS TOTAL
            FROM {table}
            WHERE "{month}" IS NOT NULL
            GROUP BY 1
            ORDER BY 1
            """
        )
        return rows

    @classmethod
    def get_ulp_ranking(cls, month_key: str | None = None):
        table = "fact_anev"
        unitup = cls._unitup_column(table)
        location = cls._location_column(table)
        month = cls._month_column(table)
        if not unitup:
            return []

        month_filter = cls._month_filter(month, month_key) if month else ""
        return cls.execute_all(
            f"""
            SELECT
                "{unitup}" AS LABEL,
                COUNT(DISTINCT COALESCE(
                    CAST("{location}" AS VARCHAR),
                    CAST("{unitup}" AS VARCHAR)
                )) AS TOTAL
            FROM {table}
            WHERE "{unitup}" IS NOT NULL
            {month_filter}
            GROUP BY "{unitup}"
            ORDER BY TOTAL DESC
            LIMIT 10
            """
        )

    @classmethod
    def get_heatmap(cls, month_key: str | None = None):
        table = "fact_anev"
        unitap = cls._unitap_column(table)
        classification = cls._classification_column(table)
        location = cls._location_column(table)
        month = cls._month_column(table)

        if not unitap or not classification:
            return []

        expression = cls._classification_sql(classification)
        month_filter = cls._month_filter(month, month_key) if month else ""

        return cls.execute_all(
            f"""
            SELECT
                CAST("{unitap}" AS VARCHAR) AS UNITAP,
                {expression} AS CATEGORY,
                COUNT(DISTINCT COALESCE(
                    CAST("{location}" AS VARCHAR),
                    CAST("{unitap}" AS VARCHAR)
                )) AS VALUE
            FROM {table}
            WHERE "{unitap}" IS NOT NULL
              AND "{classification}" IS NOT NULL
              {month_filter}
            GROUP BY 1, 2
            ORDER BY 1, VALUE DESC
            """
        )

    # ==========================================================
    # PRIORITY
    # ==========================================================

    @classmethod
    def get_priority_by_unitap(cls, month_key: str | None = None):
        """
        Priority is based on:
            exposure share × (1 + persistence rate)

        This rewards areas that are both large and persistent.
        """
        table = "fact_anev"
        unitap = cls._unitap_column(table)
        location = cls._location_column(table)
        month = cls._month_column(table)

        if not unitap:
            return []

        month_filter = cls._month_filter(month, month_key) if month else ""

        return cls.execute_all(
            f"""
            WITH base AS (
                SELECT
                    CAST("{unitap}" AS VARCHAR) AS UNITAP,
                    COUNT(DISTINCT COALESCE(
                        CAST("{location}" AS VARCHAR),
                        CAST("{unitap}" AS VARCHAR)
                    )) AS LOCATIONS
                FROM {table}
                WHERE "{unitap}" IS NOT NULL
                {month_filter}
                GROUP BY 1
            ),
            total AS (
                SELECT SUM(LOCATIONS) AS GRAND_TOTAL
                FROM base
            )
            SELECT
                b.UNITAP,
                b.LOCATIONS,
                ROUND(
                    CASE WHEN t.GRAND_TOTAL > 0
                        THEN b.LOCATIONS / t.GRAND_TOTAL * 100
                        ELSE 0
                    END,
                    2
                ) AS EXPOSURE_PCT,
                ROUND(
                    CASE WHEN t.GRAND_TOTAL > 0
                        THEN b.LOCATIONS / t.GRAND_TOTAL * 100
                        ELSE 0
                    END,
                    2
                ) AS PRIORITY_SCORE
            FROM base b
            CROSS JOIN total t
            ORDER BY PRIORITY_SCORE DESC
            """
        )

    @classmethod
    def get_priority_by_classification(cls, month_key: str | None = None):
        table = "fact_anev"
        classification = cls._classification_column(table)
        location = cls._location_column(table)
        month = cls._month_column(table)

        if not classification:
            return []

        expression = cls._classification_sql(classification)
        month_filter = cls._month_filter(month, month_key) if month else ""

        return cls.execute_all(
            f"""
            WITH base AS (
                SELECT
                    {expression} AS CLASSIFICATION,
                    COUNT(DISTINCT COALESCE(
                        CAST("{location}" AS VARCHAR),
                        {expression}
                    )) AS LOCATIONS
                FROM {table}
                WHERE "{classification}" IS NOT NULL
                {month_filter}
                GROUP BY 1
            ),
            total AS (
                SELECT SUM(LOCATIONS) AS GRAND_TOTAL
                FROM base
            )
            SELECT
                b.CLASSIFICATION,
                b.LOCATIONS,
                ROUND(
                    CASE WHEN t.GRAND_TOTAL > 0
                        THEN b.LOCATIONS / t.GRAND_TOTAL * 100
                        ELSE 0
                    END,
                    2
                ) AS EXPOSURE_PCT,
                ROUND(
                    CASE WHEN t.GRAND_TOTAL > 0
                        THEN b.LOCATIONS / t.GRAND_TOTAL * 100
                        ELSE 0
                    END,
                    2
                ) AS PRIORITY_SCORE
            FROM base b
            CROSS JOIN total t
            ORDER BY PRIORITY_SCORE DESC
            """
        )

    # ==========================================================
    # DATA SCIENCE
    # ==========================================================

    @classmethod
    def get_correlation(
        cls,
        table_name: str = "fact_anev",
        month_key: str | None = None,
    ):
        numeric_columns = cls._find_numeric_columns(table_name)
        month = cls._month_column(table_name)

        if len(numeric_columns) < 2:
            return []

        numeric_columns = numeric_columns[:20]
        month_filter = cls._month_filter(month, month_key) if month else ""
        results = []

        for index, column_a in enumerate(numeric_columns):
            for column_b in numeric_columns[index + 1:]:
                try:
                    row = cls.execute_one(
                        f"""
                        SELECT corr(
                            TRY_CAST("{column_a}" AS DOUBLE),
                            TRY_CAST("{column_b}" AS DOUBLE)
                        )
                        FROM {table_name}
                        WHERE TRY_CAST("{column_a}" AS DOUBLE) IS NOT NULL
                          AND TRY_CAST("{column_b}" AS DOUBLE) IS NOT NULL
                          {month_filter}
                        """
                    )

                    correlation = (
                        float(row[0])
                        if row and row[0] is not None
                        else None
                    )
                    if correlation is None:
                        continue

                    results.append(
                        {
                            "feature_x": column_a,
                            "feature_y": column_b,
                            "correlation": correlation,
                            "abs_correlation": abs(correlation),
                        }
                    )
                except Exception:
                    logger.exception(
                        "Correlation failed: %s vs %s",
                        column_a,
                        column_b,
                    )

        results.sort(
            key=lambda item: item["abs_correlation"],
            reverse=True,
        )
        return results

    @classmethod
    def get_linear_regression(
        cls,
        table_name: str = "fact_anev",
        month_key: str | None = None,
    ):
        numeric_columns = cls._find_numeric_columns(table_name)
        month = cls._month_column(table_name)

        if len(numeric_columns) < 2:
            return []

        numeric_columns = numeric_columns[:20]
        month_filter = cls._month_filter(month, month_key) if month else ""
        results = []

        for target in numeric_columns:
            for feature in numeric_columns:
                if feature == target:
                    continue

                try:
                    row = cls.execute_one(
                        f"""
                        SELECT
                            regr_slope(
                                TRY_CAST("{target}" AS DOUBLE),
                                TRY_CAST("{feature}" AS DOUBLE)
                            ),
                            regr_intercept(
                                TRY_CAST("{target}" AS DOUBLE),
                                TRY_CAST("{feature}" AS DOUBLE)
                            ),
                            regr_r2(
                                TRY_CAST("{target}" AS DOUBLE),
                                TRY_CAST("{feature}" AS DOUBLE)
                            ),
                            COUNT(*)
                        FROM {table_name}
                        WHERE TRY_CAST("{target}" AS DOUBLE) IS NOT NULL
                          AND TRY_CAST("{feature}" AS DOUBLE) IS NOT NULL
                          {month_filter}
                        """
                    )

                    if not row:
                        continue

                    slope = float(row[0]) if row[0] is not None else None
                    intercept = float(row[1]) if row[1] is not None else None
                    r_squared = float(row[2]) if row[2] is not None else None
                    sample_size = int(row[3] or 0)

                    if slope is None or intercept is None or r_squared is None:
                        continue
                    if sample_size < 3:
                        continue

                    results.append(
                        {
                            "feature": feature,
                            "target": target,
                            "slope": slope,
                            "intercept": intercept,
                            "r_squared": r_squared,
                            "sample_size": sample_size,
                            "p_value": None,
                        }
                    )
                except Exception:
                    logger.exception(
                        "Regression failed: %s -> %s",
                        feature,
                        target,
                    )

        results.sort(
            key=lambda item: item["r_squared"],
            reverse=True,
        )
        return results[:50]

    @classmethod
    def get_feature_importance(
        cls,
        table_name: str = "fact_anev",
        month_key: str | None = None,
    ):
        numeric_columns = cls._find_numeric_columns(table_name)
        month = cls._month_column(table_name)

        if len(numeric_columns) < 2:
            return []

        target_candidates = [
            "FINDING",
            "TEMUAN",
            "TOTAL_FINDINGS",
            "SUSPECT",
            "SUSPECT_SCORE",
            "SCORE",
            "KLASIFIKASI_SCORE",
        ]
        target = cls._find_column(table_name, target_candidates)
        if not target:
            target = numeric_columns[0]

        features = [column for column in numeric_columns if column != target]
        month_filter = cls._month_filter(month, month_key) if month else ""
        results = []

        for feature in features:
            try:
                row = cls.execute_one(
                    f"""
                    SELECT corr(
                        TRY_CAST("{feature}" AS DOUBLE),
                        TRY_CAST("{target}" AS DOUBLE)
                    )
                    FROM {table_name}
                    WHERE TRY_CAST("{feature}" AS DOUBLE) IS NOT NULL
                      AND TRY_CAST("{target}" AS DOUBLE) IS NOT NULL
                      {month_filter}
                    """
                )

                if not row or row[0] is None:
                    continue

                correlation = float(row[0])
                results.append(
                    {
                        "feature": feature,
                        "target": target,
                        "importance": abs(correlation),
                        "direction": (
                            "positive" if correlation >= 0 else "negative"
                        ),
                        "correlation": correlation,
                    }
                )
            except Exception:
                logger.exception(
                    "Feature importance failed: %s",
                    feature,
                )

        results.sort(
            key=lambda item: item["importance"],
            reverse=True,
        )
        return results[:20]

    @classmethod
    def get_data_science_summary(
        cls,
        month_key: str | None = None,
    ):
        return {
            "correlation": cls.get_correlation(
                "fact_anev",
                month_key,
            ),
            "linear_regression": cls.get_linear_regression(
                "fact_anev",
                month_key,
            ),
            "feature_importance": cls.get_feature_importance(
                "fact_anev",
                month_key,
            ),
        }

    # ==========================================================
    # COMPLETE EXECUTIVE PAYLOAD
    # ==========================================================

    @classmethod
    def get_executive_charts(
        cls,
        month_key: str | None = None,
    ) -> dict[str, Any]:
        """
        One repository call for the Executive endpoint.

        Keeps the analytical pieces together so the use case/API does not
        have to reconstruct PRA/PASCA, persistence and priority separately.
        """

        pra_pasca = cls.get_pra_pasca_suspect(month_key)
        pra_monthly = cls.get_pra_monthly(month_key)
        pasca_repeat = cls.get_pasca_repeat(month_key)
        ds = cls.get_data_science_summary(month_key)

        return {
            "bar_by_unitap": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_unit_chart(month_key)
            ],
            "pie_by_tariff": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_tariff_chart(month_key)
            ],
            "donut_by_segment": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_customer_type_summary(month_key)
            ],
            "monthly_trend": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_monthly_trend(month_key)
            ],
            "ranking_by_ulp": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_ulp_ranking(month_key)
            ],
            "heatmap_unitap_x_category": [
                {
                    "unitap": str(row[0]),
                    "category": str(row[1]),
                    "value": float(row[2] or 0),
                }
                for row in cls.get_heatmap(month_key)
            ],
            "anev_classification": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_suspect_classification(month_key)
            ],
            "anev_by_unitap": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_unit_chart(month_key)
            ],
            "anev_by_tariff": [
                {"label": str(row[0]), "value": float(row[1] or 0)}
                for row in cls.get_tariff_chart(month_key)
            ],
            "pra_monthly": pra_monthly,
            "pasca_repeat": pasca_repeat,
            "data_science": {
                **ds,
                "pra_pasca_classification": [
                    {
                        "customer_type": str(row[0]),
                        "classification": str(row[1]),
                        "total": int(row[2] or 0),
                    }
                    for row in pra_pasca
                ],
            },
            "repeat_cases": [
                {
                    "label": str(item["repeat_count"]),
                    "value": float(item["locations"]),
                }
                for item in pasca_repeat["frequency"]
                if item["repeat_count"] > 1
            ],
            "priority_by_unitap": [
                {
                    "unitap": str(row[0]),
                    "locations": int(row[1] or 0),
                    "exposure_pct": float(row[2] or 0),
                    "priority_score": float(row[3] or 0),
                }
                for row in cls.get_priority_by_unitap(month_key)
            ],
            "priority_by_classification": [
                {
                    "classification": str(row[0]),
                    "locations": int(row[1] or 0),
                    "exposure_pct": float(row[2] or 0),
                    "priority_score": float(row[3] or 0),
                }
                for row in cls.get_priority_by_classification(month_key)
            ],
        }
