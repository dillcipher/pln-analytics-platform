from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

queries = {
    "MONTH_PENGECEKAN": """
        SELECT
            CAST(MONTH AS VARCHAR) AS MONTH_VALUE,
            COUNT(*) AS JUMLAH
        FROM fact_pengecekan
        GROUP BY MONTH
        ORDER BY MONTH_VALUE
    """,

    "SAMPLE_PENGECEKAN": """
        SELECT
            IDPEL,
            WAKTU_PERIKSA,
            MONTH,
            TINDAKLANJUT_PEMERIKSAAN,
            NAMA_PETUGAS
        FROM fact_pengecekan
        WHERE WAKTU_PERIKSA IS NOT NULL
        LIMIT 10
    """,

    "COLUMNS_ANEV": """
        SELECT
            column_name,
            column_type
        FROM information_schema.columns
        WHERE table_name = 'fact_anev'
        ORDER BY ordinal_position
    """
}

for name, query in queries.items():
    print()
    print("=" * 80)
    print(name)
    print("=" * 80)

    try:
        rows = c.execute(query).fetchall()

        for row in rows:
            print(row)

    except Exception as e:
        print("ERROR:", e)

c.close()
