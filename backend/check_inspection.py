from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

queries = {
    "1_COUNT_JUNI": """
        SELECT COUNT(*)
        FROM fact_pengecekan
        WHERE CAST(MONTH AS VARCHAR) = '202606'
    """,

    "2_COUNT_PERIKSA": """
        SELECT
            COUNT(*) AS TOTAL,
            COUNT(WAKTU_PERIKSA) AS SUDAH_PERIKSA,
            COUNT(DISTINCT IDPEL) AS DISTINCT_IDPEL
        FROM fact_pengecekan
        WHERE CAST(MONTH AS VARCHAR) = '202606'
    """,

    "3_CONTOH_PENGECEKAN": """
        SELECT
            IDPEL,
            WAKTU_PERIKSA,
            MONTH
        FROM fact_pengecekan
        WHERE CAST(MONTH AS VARCHAR) = '202606'
          AND WAKTU_PERIKSA IS NOT NULL
        LIMIT 10
    """,

    "4_CONTOH_ANEV": """
        SELECT
            LOCATION_CODE,
            IDPEL,
            LOCATION_NAME,
            MONTH
        FROM fact_anev
        WHERE CAST(MONTH AS VARCHAR) = '202606'
        LIMIT 10
    """
}

for name, query in queries.items():
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    try:
        rows = c.execute(query).fetchall()

        for row in rows:
            print(row)

    except Exception as e:
        print("ERROR:", e)

c.close()
