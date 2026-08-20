from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.infrastructure.duckdb.connection import (
    dataset_exists,
    get_connection,
    read_dataset_sql,
)


_IDENTIFIER = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*$"
)


# ==========================================================
# DATASET REGISTRY
# ==========================================================

DATASETS = {
    "suspect": {
        "label": "SUSPECT — ANEV",
        "group": "SUSPECT",
        "description": (
            "Data suspect/ANEV per lokasi dan bulan."
        ),
        "source": "fact_anev",
    },
    "suspect_repeat": {
        "label": "SUSPECT — Repeat Location",
        "group": "SUSPECT",
        "description": (
            "Location yang muncul pada lebih dari satu bulan."
        ),
        "source": "fact_anev",
    },
    "suspect_inspection": {
        "label": "SUSPECT — Pemeriksaan",
        "group": "SUSPECT",
        "description": (
            "Riwayat pemeriksaan dari fact_pengecekan."
        ),
        "source": "fact_pengecekan",
    },
    "dlpd_prabayar": {
        "label": "DLPD — Prabayar",
        "group": "DLPD",
        "description": (
            "Seluruh record DLPD Prabayar."
        ),
        "source": "fact_dlpd_prabayar",
    },
    "dlpd_pascabayar": {
        "label": "DLPD — Pascabayar",
        "group": "DLPD",
        "description": (
            "Seluruh record DLPD Pascabayar."
        ),
        "source": "fact_dlpd_pascabayar",
    },
    "dlpd_combined": {
        "label": "DLPD — Gabungan",
        "group": "DLPD",
        "description": (
            "Prabayar + Pascabayar dengan JENIS_LAYANAN."
        ),
        "source": "combined_dlpd",
    },
    "dlpd_inspection": {
        "label": "DLPD — Pemeriksaan",
        "group": "DLPD",
        "description": (
            "Seluruh riwayat pemeriksaan."
        ),
        "source": "fact_pengecekan",
    },
}


# ==========================================================
# COMMON FILTERS
# ==========================================================

COMMON_FILTERS = {
    "month": "MONTH",
    "unitupi": "UNITUPI",
    "unitap": "UNITAP",
    "unitup": "UNITUP",
    "tariff": "TARIF",
    "segment": "SEGMENT",
    "suspect_name": "SUSPECT_NAME",
    "location_code": "LOCATION_CODE",
    "idpel": "IDPEL",
}


FILTER_LABELS = {
    "month": "Bulan",
    "unitupi": "UNITUPI",
    "unitap": "UNITAP",
    "unitup": "UNITUP",
    "tariff": "Tarif",
    "segment": "Segment",
    "suspect_name": "Klasifikasi Suspect",
    "location_code": "Location Code",
    "idpel": "IDPEL",
}


# ==========================================================
# HELPERS
# ==========================================================

def _safe_identifier(value: str) -> str:
    if not _IDENTIFIER.match(value):
        raise ValueError(
            f"Invalid identifier: {value}"
        )

    return value


def _exists(table: str) -> bool:
    return bool(
        dataset_exists(table)
    )


def _columns(
    conn,
    table: str,
) -> list[tuple[str, str]]:
    rows = conn.execute(
        f'DESCRIBE "{_safe_identifier(table)}"'
    ).fetchall()

    return [
        (
            str(row[0]),
            str(row[1]),
        )
        for row in rows
    ]


# ==========================================================
# SOURCE SQL
# ==========================================================

def _source_sql(
    conn,
    key: str,
    month: str | None,
) -> str:

    meta = DATASETS.get(key)

    if meta is None:
        raise KeyError(key)

    source = meta["source"]

    # ------------------------------------------------------
    # Combined DLPD
    # ------------------------------------------------------

    if source == "combined_dlpd":

        parts: list[str] = []

        if _exists(
            "fact_dlpd_prabayar"
        ):
            parts.append(
                "SELECT *, "
                "'PRABAYAR' AS JENIS_LAYANAN "
                "FROM "
                + read_dataset_sql(
                    "fact_dlpd_prabayar",
                    month,
                )
            )

        if _exists(
            "fact_dlpd_pascabayar"
        ):
            parts.append(
                "SELECT *, "
                "'PASCABAYAR' AS JENIS_LAYANAN "
                "FROM "
                + read_dataset_sql(
                    "fact_dlpd_pascabayar",
                    month,
                )
            )

        if not parts:
            return (
                "(SELECT NULL WHERE FALSE)"
            )

        return (
            "("
            + "\nUNION ALL\n".join(parts)
            + ")"
        )

    # ------------------------------------------------------
    # Normal dataset
    # ------------------------------------------------------

    if not _exists(source):
        return (
            "(SELECT NULL WHERE FALSE)"
        )

    return read_dataset_sql(
        source,
        month,
    )


# ==========================================================
# EFFECTIVE COLUMNS
# ==========================================================

def _effective_columns(
    conn,
    key: str,
) -> list[tuple[str, str]]:

    source = DATASETS[key]["source"]

    if source == "combined_dlpd":

        if _exists(
            "fact_dlpd_prabayar"
        ):
            return (
                _columns(
                    conn,
                    "fact_dlpd_prabayar",
                )
                + [
                    (
                        "JENIS_LAYANAN",
                        "VARCHAR",
                    )
                ]
            )

        if _exists(
            "fact_dlpd_pascabayar"
        ):
            return (
                _columns(
                    conn,
                    "fact_dlpd_pascabayar",
                )
                + [
                    (
                        "JENIS_LAYANAN",
                        "VARCHAR",
                    )
                ]
            )

        return []

    if not _exists(source):
        return []

    return _columns(
        conn,
        source,
    )


# ==========================================================
# WHERE BUILDER
# ==========================================================

def _where(
    columns: set[str],
    filters: dict[str, str | None],
) -> tuple[str, list[Any]]:

    clauses: list[str] = []
    params: list[Any] = []

    for key, value in filters.items():

        if (
            value is None
            or not str(value).strip()
        ):
            continue

        column = COMMON_FILTERS.get(
            key
        )

        if (
            column is None
            or column not in columns
        ):
            continue

        clauses.append(
            f'CAST(d."{_safe_identifier(column)}" AS VARCHAR) = ?'
        )

        params.append(
            str(value).strip()
        )

    if not clauses:
        return "", []

    return (
        " WHERE "
        + " AND ".join(clauses),
        params,
    )


# ==========================================================
# REPEAT QUERY
# ==========================================================

def _repeat_query(
    month: str | None,
) -> tuple[str, list[Any]]:

    if not _exists(
        "fact_anev"
    ):
        return (
            """
            SELECT
                CAST(NULL AS VARCHAR)
                    AS LOCATION_CODE,
                CAST(0 AS BIGINT)
                    AS REPEAT_COUNT
            WHERE FALSE
            """,
            [],
        )

    if month:
        clause = (
            "AND CAST(MONTH AS VARCHAR) <= ?"
        )
        params: list[Any] = [
            month
        ]
    else:
        clause = ""
        params = []

    sql = f"""
        WITH location_month AS (
            SELECT DISTINCT
                CAST(
                    LOCATION_CODE AS VARCHAR
                ) AS LOCATION_CODE,

                CAST(
                    MONTH AS VARCHAR
                ) AS MONTH

            FROM fact_anev

            WHERE
                LOCATION_CODE IS NOT NULL
                AND MONTH IS NOT NULL

                {clause}
        )

        SELECT
            LOCATION_CODE,
            COUNT(*) AS REPEAT_COUNT

        FROM location_month

        GROUP BY
            LOCATION_CODE

        HAVING
            COUNT(*) > 1

        ORDER BY
            REPEAT_COUNT DESC,
            LOCATION_CODE
    """

    return sql, params


# ==========================================================
# REPOSITORY
# ==========================================================

class DuckDbDataManagementRepository:

    # ======================================================
    # OVERVIEW
    # ======================================================

    def overview(
        self,
    ) -> dict[str, Any]:
        """
        Return lightweight metadata used by the
        Data Management landing page.

        Physical warehouse datasets are counted here.
        Derived datasets such as suspect_repeat and
        dlpd_combined are intentionally not double-counted.
        """

        conn = get_connection()

        try:
            physical_datasets = [
                (
                    "fact_anev",
                    "SUSPECT / ANEV",
                    "SUSPECT",
                ),
                (
                    "fact_dlpd_prabayar",
                    "DLPD Prabayar",
                    "DLPD",
                ),
                (
                    "fact_dlpd_pascabayar",
                    "DLPD Pascabayar",
                    "DLPD",
                ),
                (
                    "fact_pengecekan",
                    "Pemeriksaan",
                    "INSPECTION",
                ),
            ]

            datasets: list[
                dict[str, Any]
            ] = []

            total_rows = 0
            total_dataset = 0

            for (
                table_name,
                label,
                group,
            ) in physical_datasets:

                available = _exists(
                    table_name
                )

                if available:

                    columns = _columns(
                        conn,
                        table_name,
                    )

                    rows = int(
                        conn.execute(
                            f'''
                            SELECT COUNT(*)
                            FROM "{_safe_identifier(table_name)}"
                            '''
                        ).fetchone()[0]
                        or 0
                    )

                    total_rows += rows
                    total_dataset += 1

                else:

                    columns = []
                    rows = 0

                column_data = [
                    {
                        "key": name,
                        "label": name,
                        "dtype": dtype,
                    }
                    for name, dtype
                    in columns
                ]

                column_names = {
                    name
                    for name, _
                    in columns
                }

                filter_keys = [
                    key
                    for key, column
                    in COMMON_FILTERS.items()
                    if column in column_names
                ]

                datasets.append(
                    {
                        "name": table_name,
                        "label": label,
                        "group": group,
                        "rows": rows,
                        "size_mb": 0,
                        "size_bytes": 0,
                        "status": (
                            "READY"
                            if available
                            else "UNAVAILABLE"
                        ),
                        "available": available,
                        "columns": column_data,
                        "filter_keys": filter_keys,
                    }
                )

            return {
                "total_dataset": total_dataset,
                "total_rows": total_rows,
                "total_size_mb": 0,
                "total_size_bytes": 0,
                "datasets": datasets,
            }

        finally:
            conn.close()

    # ======================================================
    # CATALOG
    # ======================================================

    def catalog(
        self,
    ) -> list[dict[str, Any]]:

        conn = get_connection()

        try:

            result: list[
                dict[str, Any]
            ] = []

            for key, meta in DATASETS.items():

                cols = _effective_columns(
                    conn,
                    key,
                )

                names = {
                    name
                    for name, _
                    in cols
                }

                if meta["source"] == "combined_dlpd":

                    available = (
                        _exists(
                            "fact_dlpd_prabayar"
                        )
                        or _exists(
                            "fact_dlpd_pascabayar"
                        )
                    )

                else:

                    available = _exists(
                        meta["source"]
                    )

                result.append(
                    {
                        **meta,
                        "key": key,
                        "available": available,
                        "columns": [
                            {
                                "key": name,
                                "label": name,
                                "dtype": dtype,
                            }
                            for name, dtype
                            in cols
                        ],
                        "filter_keys": [
                            filter_key
                            for filter_key, column
                            in COMMON_FILTERS.items()
                            if column in names
                        ],
                    }
                )

            return result

        finally:
            conn.close()

    # ======================================================
    # FILTER OPTIONS
    # ======================================================

    def filter_options(
        self,
        key: str,
        month: str | None = None,
    ) -> list[dict[str, Any]]:

        conn = get_connection()

        try:

            if key not in DATASETS:
                raise KeyError(key)

            names = {
                name
                for name, _
                in _effective_columns(
                    conn,
                    key,
                )
            }

            source = _source_sql(
                conn,
                key,
                month,
            )

            result: list[
                dict[str, Any]
            ] = []

            for (
                filter_key,
                column,
            ) in COMMON_FILTERS.items():

                if column not in names:
                    continue

                sql = (
                    f'SELECT DISTINCT '
                    f'CAST(d."'
                    f'{_safe_identifier(column)}'
                    f'" AS VARCHAR) '
                    f'FROM {source} d '
                    f'WHERE d."'
                    f'{_safe_identifier(column)}'
                    f'" IS NOT NULL '
                    f'ORDER BY 1 '
                    f'LIMIT 500'
                )

                values = [
                    str(row[0])
                    for row
                    in conn.execute(
                        sql
                    ).fetchall()
                    if row[0] is not None
                ]

                result.append(
                    {
                        "key": filter_key,
                        "label": FILTER_LABELS.get(
                            filter_key,
                            filter_key,
                        ),
                        "values": values,
                    }
                )

            return result

        finally:
            conn.close()

    # ======================================================
    # PREVIEW
    # ======================================================

    def preview(
        self,
        key: str,
        month: str | None,
        filters: dict[
            str,
            str | None,
        ],
        limit: int = 100,
    ) -> dict[str, Any]:

        conn = get_connection()

        try:

            # --------------------------------------------------
            # Repeat location
            # --------------------------------------------------

            if key == "suspect_repeat":

                sql, params = _repeat_query(
                    month
                )

                safe_limit = min(
                    max(int(limit), 1),
                    500,
                )

                rows = conn.execute(
                    sql + " LIMIT ?",
                    params + [safe_limit],
                ).fetchall()

                names = [
                    "LOCATION_CODE",
                    "REPEAT_COUNT",
                ]

                return {
                    "dataset": key,
                    "columns": [
                        {
                            "key": "LOCATION_CODE",
                            "label": "LOCATION_CODE",
                            "dtype": "VARCHAR",
                        },
                        {
                            "key": "REPEAT_COUNT",
                            "label": "REPEAT_COUNT",
                            "dtype": "BIGINT",
                        },
                    ],
                    "rows": [
                        dict(
                            zip(
                                names,
                                row,
                            )
                        )
                        for row in rows
                    ],
                    "total_rows": len(rows),
                }

            # --------------------------------------------------
            # Normal datasets
            # --------------------------------------------------

            if key not in DATASETS:
                raise KeyError(key)

            cols = _effective_columns(
                conn,
                key,
            )

            names = [
                name
                for name, _
                in cols
            ]

            if not names:
                return {
                    "dataset": key,
                    "columns": [],
                    "rows": [],
                    "total_rows": 0,
                }

            source = _source_sql(
                conn,
                key,
                month,
            )

            where, params = _where(
                set(names),
                filters,
            )

            select_sql = ", ".join(
                f'd."{_safe_identifier(name)}"'
                for name in names
            )

            total = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {source} d
                    {where}
                    """,
                    params,
                ).fetchone()[0]
                or 0
            )

            safe_limit = min(
                max(int(limit), 1),
                500,
            )

            rows = conn.execute(
                f"""
                SELECT
                    {select_sql}
                FROM {source} d
                {where}
                LIMIT ?
                """,
                params + [safe_limit],
            ).fetchall()

            return {
                "dataset": key,
                "columns": [
                    {
                        "key": name,
                        "label": name,
                        "dtype": dtype,
                    }
                    for name, dtype
                    in cols
                ],
                "rows": [
                    dict(
                        zip(
                            names,
                            row,
                        )
                    )
                    for row in rows
                ],
                "total_rows": total,
            }

        finally:
            conn.close()

    # ======================================================
    # CSV EXPORT
    # ======================================================

    def export_csv(
        self,
        key: str,
        month: str | None,
        filters: dict[
            str,
            str | None,
        ],
        selected_columns: list[
            str
        ] | None = None,
    ) -> tuple[
        bytes,
        str,
    ]:

        conn = get_connection()

        try:

            # --------------------------------------------------
            # Repeat location
            # --------------------------------------------------

            if key == "suspect_repeat":

                sql, params = _repeat_query(
                    month
                )

                rows = conn.execute(
                    sql,
                    params,
                ).fetchall()

                names = [
                    "LOCATION_CODE",
                    "REPEAT_COUNT",
                ]

            else:

                if key not in DATASETS:
                    raise KeyError(key)

                cols = _effective_columns(
                    conn,
                    key,
                )

                available = [
                    name
                    for name, _
                    in cols
                ]

                if not available:
                    raise ValueError(
                        "Dataset tidak memiliki kolom."
                    )

                if selected_columns:

                    invalid = (
                        set(selected_columns)
                        - set(available)
                    )

                    if invalid:
                        raise ValueError(
                            "Unknown export columns: "
                            + ", ".join(
                                sorted(
                                    invalid
                                )
                            )
                        )

                    wanted = set(
                        selected_columns
                    )

                    names = [
                        name
                        for name
                        in available
                        if name in wanted
                    ]

                    if not names:
                        raise ValueError(
                            "Tidak ada kolom export yang dipilih."
                        )

                else:

                    names = available

                source = _source_sql(
                    conn,
                    key,
                    month,
                )

                where, params = _where(
                    set(available),
                    filters,
                )

                select_sql = ", ".join(
                    f'd."{_safe_identifier(name)}"'
                    for name in names
                )

                rows = conn.execute(
                    f"""
                    SELECT
                        {select_sql}
                    FROM {source} d
                    {where}
                    """,
                    params,
                ).fetchall()

            # --------------------------------------------------
            # CSV
            # --------------------------------------------------

            output = io.StringIO(
                newline=""
            )

            writer = csv.writer(
                output
            )

            writer.writerow(
                names
            )

            writer.writerows(
                rows
            )

            filename = (
                f"{key}_"
                f"{month or 'all'}.csv"
            )

            return (
                output
                .getvalue()
                .encode("utf-8-sig"),
                filename,
            )

        finally:
            conn.close()

    # ======================================================
    # STATUS
    # ======================================================

    def status(
        self,
    ) -> dict[str, Any]:

        conn = get_connection()

        try:

            names = [
                "fact_anev",
                "fact_dlpd_prabayar",
                "fact_dlpd_pascabayar",
                "fact_pengecekan",
            ]

            datasets: list[
                dict[str, Any]
            ] = []

            for name in names:

                if not _exists(name):

                    datasets.append(
                        {
                            "name": name,
                            "rows": 0,
                            "size_bytes": 0,
                            "available": False,
                        }
                    )

                    continue

                rows = int(
                    conn.execute(
                        f'''
                        SELECT COUNT(*)
                        FROM "{_safe_identifier(name)}"
                        '''
                    ).fetchone()[0]
                    or 0
                )

                datasets.append(
                    {
                        "name": name,
                        "rows": rows,
                        "size_bytes": 0,
                        "available": True,
                    }
                )

            return {
                "datasets": datasets,
                "total_datasets": sum(
                    1
                    for item in datasets
                    if item["available"]
                ),
                "total_rows": sum(
                    item["rows"]
                    for item in datasets
                ),
                "total_size_bytes": 0,
            }

        finally:
            conn.close()