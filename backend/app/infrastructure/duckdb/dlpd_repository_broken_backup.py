from __future__ import annotations

from typing import Any

from app.core.month_utils import month_keys_to_options
from app.domain.entities import (
    DlpdCustomerDetail,
    DlpdDashboard,
    DlpdDashboardUlp,
    InspectionHistory,
    MonthOption,
    PageResult,
)
from app.domain.repositories import (
    CustomerType,
    DlpdFilters,
    DlpdRepository,
)
from app.infrastructure.duckdb.connection import get_connection
from app.infrastructure.duckdb.query_helpers import (
    build_equality_filters,
    build_search_clause,
    paginate,
)


_FILTER_COLUMN_MAP = {
    "unitupi": "d.UNITUPI",
    "unitap": "d.UNITAP",
    "unitup": "d.UNITUP",
    "tariff": "d.TARIF",
}


class DuckDbDlpdRepository(DlpdRepository):

    # ==========================================================
    # INTERNAL
    # ==========================================================

    @staticmethod
    def _table(
        customer_type: CustomerType,
    ) -> str:

        if customer_type == "prabayar":
            return "fact_dlpd_prabayar"

        return "fact_dlpd_pascabayar"

    @staticmethod
    def _inspection_cte() -> str:
        """
        Ambil satu record pengecekan terbaru untuk setiap IDPEL
        hanya dari bulan yang sedang dipilih.

        Placeholder pertama pada query adalah month_key (YYYYMM).
        Dengan begitu pemeriksaan dari bulan lain tidak ikut menentukan
        status dashboard, ULP, customer list, atau detail bulan terpilih.
        """

        return """
        latest_inspection AS (

            SELECT
                IDPEL,
                STATUSKWH,
                UPDATESTATUS,
                CATATAN,
                NAMAPETUGAS,
                REGU,
                WAKTUPERIKSA,
                TINDAKLANJUTPEMERIKSAAN,

                ROW_NUMBER() OVER (
                    PARTITION BY IDPEL
                    ORDER BY
                        WAKTUPERIKSA DESC NULLS LAST
                ) AS rn

            FROM fact_pengecekan

            WHERE
                strftime(
                    TRY_CAST(WAKTUPERIKSA AS TIMESTAMP),
                    '%Y%m'
                ) = ?
        )
        """

    @staticmethod
    def _status_case() -> str:

        return """
        CASE

            WHEN p.IDPEL IS NULL
                THEN 'BELUM'

            WHEN UPPER(
                COALESCE(
                    p.STATUSKWH,
                    p.UPDATESTATUS,
                    ''
                )
            ) LIKE '%NORMAL%'
                THEN 'NORMAL'

            ELSE 'TEMUAN'

        END
        """

    @staticmethod
    def _previous_months(
        month_key: str,
        total: int = 6,
    ) -> list[str]:

        month_key = str(month_key)

        if len(month_key) != 6:
            return [month_key]

        year = int(month_key[:4])
        month = int(month_key[4:])

        result: list[str] = []

        for _ in range(total):

            result.append(
                f"{year:04d}{month:02d}"
            )

            month -= 1

            if month == 0:

                month = 12
                year -= 1

        result.reverse()

        return result

    def _repeat_cte(
        self,
        customer_type: CustomerType,
        month_key: str,
    ) -> tuple[str, list[Any]]:

        table = self._table(
            customer_type,
        )

        months = self._previous_months(
            month_key,
            6,
        )

        placeholders = ",".join(
            "?"
            for _ in months
        )

        sql = f"""
        repeat_history AS (

            SELECT

                IDPEL,

                COUNT(*) AS REPEAT_COUNT

            FROM {table}

            WHERE CAST(MONTH AS VARCHAR)
                IN ({placeholders})

            GROUP BY IDPEL

        )
        """

        return (
            sql,
            months,
        )

    def _build_where(
        self,
        month_key: str,
        filters: DlpdFilters,
    ) -> tuple[str, list[Any]]:

        clauses = [
            "CAST(d.MONTH AS VARCHAR) = ?",
        ]

        params: list[Any] = [
            str(month_key),
        ]

        mapping = {
            "unitupi": "d.UNITUPI",
            "unitap": "d.UNITAP",
            "unitup": "d.UNITUP",
            "tariff": "d.TARIF",
        }

        equality_sql, equality_params = (
            build_equality_filters(
                {
                    "unitupi": filters.unitupi,
                    "unitap": filters.unitap,
                    "unitup": filters.unitup,
                    "tariff": filters.tariff,
                },
                mapping,
            )
        )

        if equality_sql:

            cleaned = (
                equality_sql
                .replace("AND ", "")
                .strip()
            )

            if cleaned:
                clauses.append(cleaned)

            params.extend(
                equality_params,
            )

        search_sql, search_params = (
            build_search_clause(
                (
                    filters.search_idpel
                    or filters.search_nama
                ),
                [
                    "CAST(d.IDPEL AS VARCHAR)",
                    "d.NAMA",
                ],
            )
        )

        if search_sql:

            cleaned = (
                search_sql
                .replace("AND ", "")
                .strip()
            )

            if cleaned:
                clauses.append(cleaned)

            params.extend(
                search_params,
            )

        if filters.status:

            normalized_status = (
                filters.status
                .strip()
                .lower()
            )

            if normalized_status == "normal":

                clauses.append(
                    """
                    UPPER(
                        COALESCE(
                            p.STATUSKWH,
                            p.UPDATESTATUS,
                            ''
                        )
                    ) LIKE '%NORMAL%'
                    """
                )

            elif normalized_status == "temuan":

                clauses.append(
                    """
                    p.IDPEL IS NOT NULL
                    AND UPPER(
                        COALESCE(
                            p.STATUSKWH,
                            p.UPDATESTATUS,
                            ''
                        )
                    ) NOT LIKE '%NORMAL%'
                    """
                )

            elif normalized_status in (
                "belum",
                "belum periksa",
            ):

                clauses.append(
                    "p.IDPEL IS NULL"
                )

        return (
            "WHERE "
            + "\nAND ".join(
                clauses,
            ),
            params,
        )

    # ==========================================================
    # MONTH
    # ==========================================================

    def get_available_months(
        self,
        customer_type: CustomerType,
    ) -> list[MonthOption]:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        rows = conn.execute(
            f"""
            SELECT

                CAST(MONTH AS VARCHAR) AS MONTH,

                COUNT(*) AS TOTAL

            FROM {table}

            WHERE
                MONTH IS NOT NULL
                AND TRIM(
                    CAST(MONTH AS VARCHAR)
                ) <> ''

            GROUP BY
                CAST(MONTH AS VARCHAR)

            ORDER BY
                CAST(MONTH AS VARCHAR)
            """
        ).fetchall()

        return month_keys_to_options(
            [
                str(row[0])
                for row in rows
            ]
        )

    # ==========================================================
    # FILTER
    # ==========================================================

    def get_filter_options(
        self,
        customer_type: CustomerType,
        month_key: str | None,
    ) -> dict[str, list[str]]:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        where = ""
        params: list[Any] = []

        if month_key:

            where = """
            WHERE CAST(MONTH AS VARCHAR) = ?
            """

            params.append(
                str(month_key),
            )

        def distinct(
            column: str,
        ) -> list[str]:

            sql = f"""
            SELECT DISTINCT

                {column}

            FROM {table}

            {where}
            """

            rows = conn.execute(
                sql,
                params,
            ).fetchall()

            return sorted(
                str(row[0])
                for row in rows
                if row[0] not in (
                    None,
                    "",
                )
            )

        repeat_values: list[str] = []

        if month_key:

            repeat_cte, repeat_params = (
                self._repeat_cte(
                    customer_type,
                    month_key,
                )
            )

            rows = conn.execute(
                f"""
                WITH

                {repeat_cte}

                SELECT DISTINCT

                    REPEAT_COUNT

                FROM repeat_history

                ORDER BY
                    REPEAT_COUNT
                """,
                repeat_params,
            ).fetchall()

            repeat_values = [
                str(row[0])
                for row in rows
            ]

        result = {

            "months": [
                month.month_key
                for month in self.get_available_months(
                    customer_type,
                )
            ],

            "unitupi": [],

            "unitap": distinct(
                "UNITAP",
            ),

            "unitup": distinct(
                "UNITUP",
            ),

            "tariff": distinct(
                "TARIF",
            ),

            "status": [
                "BELUM",
                "NORMAL",
                "TEMUAN",
            ],

            "dlpd_repeat": repeat_values,

        }

        if customer_type == "prabayar":

            result["unitupi"] = distinct(
                "UNITUPI",
            )

        return result

    # ==========================================================
    # DASHBOARD KPI
    # ==========================================================

    def get_dashboard(
        self,
        customer_type: CustomerType,
        month_key: str,
        filters: DlpdFilters,
    ) -> dict[str, Any]:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        where_sql, params = self._build_where(
            month_key,
            filters,
        )

        sql = f"""
        WITH

        {self._inspection_cte()}

        SELECT

            COUNT(*) AS total_target,

            SUM(
                CASE
                    WHEN UPPER(
                        COALESCE(
                            p.STATUSKWH,
                            p.UPDATESTATUS,
                            ''
                        )
                    ) LIKE '%NORMAL%'
                    THEN 1
                    ELSE 0
                END
            ) AS normal,

            SUM(
                CASE
                    WHEN p.IDPEL IS NOT NULL
                    AND UPPER(
                        COALESCE(
                            p.STATUSKWH,
                            p.UPDATESTATUS,
                            ''
                        )
                    ) NOT LIKE '%NORMAL%'
                    THEN 1
                    ELSE 0
                END
            ) AS temuan,

            SUM(
                CASE
                    WHEN p.IDPEL IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS belum_periksa

        FROM {table} d

        LEFT JOIN latest_inspection p

            ON d.IDPEL = p.IDPEL

            AND p.rn = 1

        {where_sql}
        """

        row = conn.execute(
            sql,
            [str(month_key), *params],
        ).fetchone()

        if row is None:

            return {
                "total_target": 0,
                "normal": 0,
                "temuan": 0,
                "belum_periksa": 0,
                "sudah_periksa": 0,
                "progress_pct": 0.0,
            }

        total = int(row[0] or 0)
        normal = int(row[1] or 0)
        temuan = int(row[2] or 0)
        belum = int(row[3] or 0)

        # Sudah diperiksa = total target - belum diperiksa
        sudah_periksa = max(
            total - belum,
            0,
        )

        progress = (
            sudah_periksa / total * 100
            if total > 0
            else 0.0
        )

        return {
            "total_target": total,
            "normal": normal,
            "temuan": temuan,
            "belum_periksa": belum,
            "sudah_periksa": sudah_periksa,
            "progress_pct": round(
                progress,
                2,
            ),
        }

    # ==========================================================
    # DASHBOARD ULP
    # ==========================================================

    def get_dashboard_ulp(
        self,
        customer_type: CustomerType,
        month_key: str,
        filters: DlpdFilters,
    ) -> list[dict]:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        where_sql, params = self._build_where(
            month_key,
            filters,
        )

        extra_sql = ""

        if customer_type == "pascabayar":

            extra_sql = """

            ,

            SUM(
                CASE
                    WHEN d.DLPD < 40
                    THEN 1
                    ELSE 0
                END
            ) AS kwh_lt40,

            SUM(
                CASE
                    WHEN d.DLPD = 0
                    THEN 1
                    ELSE 0
                END
            ) AS kwh_zero

            """

        sql = f"""
        WITH

        {self._inspection_cte()}

        SELECT

            d.UNITUP,

            d.UNITUP AS unit_name,

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN UPPER(
                        COALESCE(
                            p.STATUSKWH,
                            p.UPDATESTATUS,
                            ''
                        )
                    ) LIKE '%NORMAL%'
                    THEN 1
                    ELSE 0
                END
            ) AS normal,

            SUM(
                CASE
                    WHEN p.IDPEL IS NOT NULL
                    AND UPPER(
                        COALESCE(
                            p.STATUSKWH,
                            p.UPDATESTATUS,
                            ''
                        )
                    ) NOT LIKE '%NORMAL%'
                    THEN 1
                    ELSE 0
                END
            ) AS temuan,

            SUM(
                CASE
                    WHEN p.IDPEL IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS belum_periksa

            {extra_sql}

        FROM {table} d

        LEFT JOIN latest_inspection p

            ON d.IDPEL = p.IDPEL

            AND p.rn = 1

        {where_sql}

        GROUP BY
            d.UNITUP

        ORDER BY
            d.UNITUP
        """

        rows = conn.execute(
            sql,
            [str(month_key), *params],
        ).fetchall()

        result = []

        for row in rows:

            total = row[2] or 0
            normal = row[3] or 0
            temuan = row[4] or 0
            belum = row[5] or 0

            inspected = normal + temuan

            percentage = (
                inspected / total * 100
                if total
                else 0
            )

            item = {

                "unitup": str(
                    row[0]
                ),

                "unit_name": str(
                    row[1]
                ),

                "total": total,

                "normal": normal,

                "temuan": temuan,

                "belum_periksa": belum,

                "total_pemeriksaan": inspected,

                "percentage": round(
                    percentage,
                    2,
                ),

            }

            if customer_type == "pascabayar":

                item["kwh_lt40"] = (
                    row[6] or 0
                )

                item["kwh_zero"] = (
                    row[7] or 0
                )

            result.append(
                item,
            )

        return result

    # ==========================================================
    # CUSTOMER LIST
    # ==========================================================

    def get_customers(
        self,
        customer_type: CustomerType,
        month_key: str,
        filters: DlpdFilters,
        page: int,
        page_size: int,
    ) -> PageResult:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        where_sql, params = self._build_where(
            month_key,
            filters,
        )

        offset, page_size = paginate(
            page,
            page_size,
            500,
        )

        if customer_type == "prabayar":

            unitupi_sql = "d.UNITUPI"

        else:

            unitupi_sql = "NULL"

        repeat_cte, repeat_params = (
            self._repeat_cte(
                customer_type,
                month_key,
            )
        )

        sql = f"""
        WITH

        {self._inspection_cte()},

        {repeat_cte}

        SELECT

            d.IDPEL,

            d.NAMA,

            {unitupi_sql} AS UNITUPI,

            d.UNITAP,

            d.UNITUP,

            d.TARIF,

            d.DAYA,

            d.ALAMAT,

            CASE

                WHEN p.IDPEL IS NULL
                    THEN 'Belum Periksa'

                WHEN UPPER(
                    COALESCE(
                        p.STATUSKWH,
                        p.UPDATESTATUS,
                        ''
                    )
                ) LIKE '%NORMAL%'
                    THEN 'Normal'

                ELSE 'Temuan'

            END AS STATUS,

            COALESCE(
                r.repeat_count,
                1
            ) AS DLPD_REPEAT,

            p.STATUSKWH,

            p.CATATAN,

            p.NAMAPETUGAS,

            p.REGU,

            p.WAKTUPERIKSA,

            p.TINDAKLANJUTPEMERIKSAAN

        FROM {table} d

        LEFT JOIN latest_inspection p

            ON d.IDPEL = p.IDPEL

            AND p.rn = 1

        LEFT JOIN repeat_history r

            ON d.IDPEL = r.IDPEL

        {where_sql}
        """

        count_params = (
            list(params)
        )

        if filters.dlpd_repeat:

            repeat_value = int(
                filters.dlpd_repeat,
            )

            sql += """

            AND COALESCE(
                r.repeat_count,
                1
            ) = ?

            """

            params.append(
                repeat_value,
            )

            count_params.append(
                repeat_value,
            )

        sql += """

        ORDER BY

            d.UNITUP,

            d.NAMA

        LIMIT ?

        OFFSET ?

        """

        params.extend(
            [
                page_size,
                offset,
            ]
        )

        rows = conn.execute(
            sql,
            [
                str(month_key),
                *repeat_params,
                *params,
            ],
        ).fetchall()

        count_sql = f"""
        WITH

        {self._inspection_cte()},

        {repeat_cte}

        SELECT

            COUNT(*)

        FROM {table} d

        LEFT JOIN latest_inspection p

            ON d.IDPEL = p.IDPEL

            AND p.rn = 1

        LEFT JOIN repeat_history r

            ON d.IDPEL = r.IDPEL

        {where_sql}
        """

        if filters.dlpd_repeat:

            count_sql += """

            AND COALESCE(
                r.repeat_count,
                1
            ) = ?

            """

        total_row = conn.execute(
            count_sql,
            [
                str(month_key),
                *repeat_params,
                *count_params,
            ],
        ).fetchone()

        total_rows = (
            total_row[0]
            if total_row is not None
            else 0
        )

        items = []

        for row in rows:

            items.append(

                {

                    "idpel": str(
                        row[0]
                    ),

                    "nama": row[1],

                    "unitupi": row[2],

                    "unitap": row[3],

                    "unitup": row[4],

                    "tariff": row[5],

                    "daya": row[6],

                    "alamat": row[7],

                    "status": row[8],

                    "dlpd_repeat": str(
                        row[9]
                    ),

                    "kategori": row[10],

                    "keterangan": None,

                    "alasan": None,

                    "catatan": row[11],

                    "petugas": row[12],

                    "regu": row[13],

                    "waktu_periksa": row[14],

                }

            )

        return PageResult(
        items=items,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
    )

    # ==========================================================
    # CUSTOMER DETAIL
    # ==========================================================

    def get_customer_detail(
        self,
        customer_type: CustomerType,
        idpel: str,
        month_key: str,
    ) -> dict | None:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        sql = f"""
        WITH

        {self._inspection_cte()}

        SELECT

            d.*,

            CASE

                WHEN p.IDPEL IS NULL
                    THEN 'Belum Periksa'

                WHEN UPPER(
                    COALESCE(
                        p.STATUSKWH,
                        p.UPDATESTATUS,
                        ''
                    )
                ) LIKE '%NORMAL%'
                    THEN 'Normal'

                ELSE 'Temuan'

            END AS status,

            p.STATUSKWH,

            p.CATATAN,

            p.NAMAPETUGAS,

            p.REGU,

            p.WAKTUPERIKSA,

            p.TINDAKLANJUTPEMERIKSAAN

        FROM {table} d

        LEFT JOIN latest_inspection p

            ON d.IDPEL = p.IDPEL

            AND p.rn = 1

        WHERE

            CAST(d.MONTH AS VARCHAR) = ?

            AND CAST(d.IDPEL AS VARCHAR) = ?

        LIMIT 1
        """

        row = conn.execute(
            sql,
            [
                str(month_key),
                str(month_key),
                str(idpel),
            ],
        ).fetchone()

        if row is None:

            return None

        columns = [
            c[0]
            for c in conn.description
        ]

        customer = dict(
            zip(
                columns,
                row,
            )
        )

        history_sql = """
        SELECT

            WAKTUPERIKSA,

            STATUSKWH,

            NAMAPETUGAS,

            REGU,

            CATATAN,

            TINDAKLANJUTPEMERIKSAAN

        FROM fact_pengecekan

        WHERE CAST(IDPEL AS VARCHAR) = ?

        ORDER BY
            WAKTUPERIKSA DESC
        """

        history_rows = conn.execute(
            history_sql,
            [
                str(idpel),
            ],
        ).fetchall()

        history = []

        for item in history_rows:

            history.append(

                InspectionHistory(

                    waktu_periksa=item[0],

                    status=item[1],

                    petugas=item[2],

                    regu=item[3],

                    catatan=item[4],

                    tindak_lanjut=item[5],

                )

            )

        return DlpdCustomerDetail(

            customer=customer,

            inspection_history=history,

        )

    # ==========================================================
    # EXPORT
    # ==========================================================

    def export_customers(
        self,
        customer_type: str,
        month_key: str,
        filters: DlpdFilters,
    ) -> list[dict]:

        conn = get_connection()

        table = self._table(
            customer_type,
        )

        where_sql, params = self._build_where(
            month_key,
            filters,
        )

        sql = f"""
        WITH

        {self._inspection_cte()}

        SELECT

            d.IDPEL,

            d.NAMA,

            d.ALAMAT,

            d.UNITUPI,

            d.UNITAP,

            d.UNITUP,

            d.TARIF,

            d.DAYA,

            d.DLPD,

            CASE

                WHEN p.IDPEL IS NULL
                    THEN 'Belum Periksa'

                WHEN UPPER(
                    COALESCE(
                        p.STATUSKWH,
                        p.UPDATESTATUS,
                        ''
                    )
                ) LIKE '%NORMAL%'
                    THEN 'Normal'

                ELSE 'Temuan'

            END AS STATUS,

            p.WAKTUPERIKSA,

            p.UPDATESTATUS,

            p.NAMAPETUGAS,

            p.REGU

        FROM {table} d

        LEFT JOIN latest_inspection p

            ON d.IDPEL = p.IDPEL

            AND p.rn = 1

        {where_sql}

        ORDER BY

            d.UNITUP,

            d.NAMA
        """

        rows = conn.execute(
            sql,
            [str(month_key), *params],
        ).fetchall()

        columns = [
            c[0].lower()
            for c in conn.description
        ]

        return [

            dict(
                zip(
                    columns,
                    row,
                )
            )

            for row in rows

        ]