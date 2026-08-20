from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

queries = {
    "KANDIDAT_KOLOM_ANEV": """
        SELECT
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_name = 'fact_anev'
          AND (
              UPPER(column_name) LIKE '%ID%'
              OR UPPER(column_name) LIKE '%PEL%'
              OR UPPER(column_name) LIKE '%LOCATION%'
              OR UPPER(column_name) LIKE '%PELANGGAN%'
          )
        ORDER BY ordinal_position
    """,

    "SAMPLE_ANEV": """
        SELECT *
        FROM fact_anev
        WHERE CAST(MONTH AS VARCHAR) = '202606'
        LIMIT 2
    """,

    "PENGECEKAN_BY_MONTH": """
        SELECT
            STRFTIME(WAKTU_PERIKSA, '%Y%m') AS BULAN,
            COUNT(*) AS JUMLAH,
            COUNT(DISTINCT IDPEL) AS IDPEL_UNIK
        FROM fact_pengecekan
        WHERE WAKTU_PERIKSA IS NOT NULL
        GROUP BY STRFTIME(WAKTU_PERIKSA, '%Y%m')
        ORDER BY BULAN
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
