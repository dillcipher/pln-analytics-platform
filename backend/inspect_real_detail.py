from app.infrastructure.duckdb.connection import (
    get_connection,
    read_dataset_sql,
)


c = get_connection()

month_key = "202606"

detail_source = read_dataset_sql(
    "suspect_detail",
    month_key,
)

print("=" * 80)
print("REAL SUSPECT DETAIL SOURCE")
print("=" * 80)
print(detail_source)

queries = [
    (
        "DETAIL TOTAL",
        f"""
        SELECT COUNT(*)
        FROM {detail_source}
        WHERE CAST(MONTH_KEY AS VARCHAR) = ?
        """,
        [month_key],
    ),

    (
        "DETAIL OVER VOLTAGE",
        f"""
        SELECT COUNT(*)
        FROM {detail_source}
        WHERE CAST(MONTH_KEY AS VARCHAR) = ?
          AND CAST(LOCATION_CODE AS VARCHAR) IN (
              SELECT DISTINCT
                  CAST(LOCATION_CODE AS VARCHAR)
              FROM fact_anev
              WHERE CAST(MONTH AS VARCHAR) = ?
                AND UPPER(
                    CAST(SUSPECT_NAME AS VARCHAR)
                ) LIKE '%OVER VOLTAGE BY INSTANT%'
          )
        """,
        [month_key, month_key],
    ),

    (
        "FINAL CLASSIFICATION JOIN",
        f"""
        SELECT COUNT(*)
        FROM {detail_source} s
        INNER JOIN (
            SELECT DISTINCT
                CAST(LOCATION_CODE AS VARCHAR)
                    AS LOCATION_CODE,
                CAST(MONTH AS VARCHAR)
                    AS MONTH_KEY
            FROM fact_anev
            WHERE CAST(MONTH AS VARCHAR) = ?
              AND SUSPECT_NAME IS NOT NULL
              AND UPPER(
                    CAST(SUSPECT_NAME AS VARCHAR)
                  ) LIKE '%OVER VOLTAGE BY INSTANT%'
        ) a
            ON CAST(s.LOCATION_CODE AS VARCHAR)
                = a.LOCATION_CODE
           AND CAST(s.MONTH_KEY AS VARCHAR)
                = a.MONTH_KEY
        WHERE CAST(s.MONTH_KEY AS VARCHAR) = ?
        """,
        [month_key, month_key],
    ),

    (
        "DETAIL SAMPLE",
        f"""
        SELECT
            *
        FROM {detail_source}
        WHERE CAST(MONTH_KEY AS VARCHAR) = ?
        LIMIT 3
        """,
        [month_key],
    ),
]


for title, query, params in queries:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    try:
        rows = c.execute(
            query,
            params,
        ).fetchall()

        for row in rows:
            print(row)

    except Exception as exc:
        print(
            "ERROR:",
            repr(exc),
        )


c.close()