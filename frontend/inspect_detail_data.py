from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

queries = [
    """
    SELECT
        COUNT(*)
    FROM fact_anev
    WHERE bulan = '202606'
      AND UPPER(CAST(SUSPECT_NAME AS VARCHAR))
          LIKE '%OVER VOLTAGE BY INSTANT%'
    """,

    """
    SELECT
        SUSPECT_NAME,
        COUNT(*)
    FROM fact_anev
    WHERE bulan = '202606'
      AND UPPER(CAST(SUSPECT_NAME AS VARCHAR))
          LIKE '%OVER VOLTAGE BY INSTANT%'
    GROUP BY SUSPECT_NAME
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """,

    """
    SELECT
        COUNT(*)
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
      AND WAKTU_PERIKSA <  TIMESTAMP '2026-07-01'
    """,
]

for i, q in enumerate(queries, 1):
    print()
    print("=" * 80)
    print("QUERY", i)
    print("=" * 80)

    try:
        rows = c.execute(q).fetchall()
        for row in rows:
            print(row)
    except Exception as e:
        print("ERROR:", repr(e))

c.close()
