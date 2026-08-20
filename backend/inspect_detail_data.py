from app.infrastructure.duckdb.connection import get_connection


c = get_connection()


queries = [
    (
        "ANE V - OVER VOLTAGE",
        """
        SELECT
            COUNT(*)
        FROM fact_anev
        WHERE CAST(MONTH AS VARCHAR) = '202606'
          AND UPPER(CAST(SUSPECT_NAME AS VARCHAR))
              LIKE '%OVER VOLTAGE BY INSTANT%'
        """,
    ),

    (
        "ANE V - CLASSIFICATION SAMPLE",
        """
        SELECT
            CAST(SUSPECT_NAME AS VARCHAR) AS SUSPECT_NAME,
            COUNT(DISTINCT CAST(LOCATION_CODE AS VARCHAR)) AS LOCATIONS
        FROM fact_anev
        WHERE CAST(MONTH AS VARCHAR) = '202606'
          AND UPPER(CAST(SUSPECT_NAME AS VARCHAR))
              LIKE '%OVER VOLTAGE BY INSTANT%'
        GROUP BY SUSPECT_NAME
        ORDER BY LOCATIONS DESC
        LIMIT 20
        """,
    ),

    (
        "SUSPECT DETAIL - TOTAL JUNI",
        """
        SELECT
            COUNT(*)
        FROM suspect_detail
        WHERE CAST(MONTH_KEY AS VARCHAR) = '202606'
        """,
    ),

    (
        "SUSPECT DETAIL - OVER VOLTAGE",
        """
        SELECT
            COUNT(*)
        FROM suspect_detail
        WHERE CAST(MONTH_KEY AS VARCHAR) = '202606'
          AND CAST(LOCATION_CODE AS VARCHAR) IN (
              SELECT DISTINCT
                  CAST(LOCATION_CODE AS VARCHAR)
              FROM fact_anev
              WHERE CAST(MONTH AS VARCHAR) = '202606'
                AND UPPER(CAST(SUSPECT_NAME AS VARCHAR))
                    LIKE '%OVER VOLTAGE BY INSTANT%'
          )
        """,
    ),

    (
        "JOIN FINAL",
        """
        SELECT
            COUNT(*)
        FROM suspect_detail s
        INNER JOIN (
            SELECT DISTINCT
                CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE,
                CAST(MONTH AS VARCHAR) AS MONTH_KEY
            FROM fact_anev
            WHERE CAST(MONTH AS VARCHAR) = '202606'
              AND SUSPECT_NAME IS NOT NULL
              AND UPPER(CAST(SUSPECT_NAME AS VARCHAR))
                  LIKE '%OVER VOLTAGE BY INSTANT%'
        ) a
            ON CAST(s.LOCATION_CODE AS VARCHAR) = a.LOCATION_CODE
           AND CAST(s.MONTH_KEY AS VARCHAR) = a.MONTH_KEY
        WHERE CAST(s.MONTH_KEY AS VARCHAR) = '202606'
        """,
    ),
]


for title, query in queries:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    try:
        rows = c.execute(query).fetchall()

        for row in rows:
            print(row)

    except Exception as exc:
        print("ERROR:", repr(exc))


c.close()