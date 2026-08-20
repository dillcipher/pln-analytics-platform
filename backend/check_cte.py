from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
WITH inspection_by_idpel AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(IDPEL AS VARCHAR)),
            '\\.0$',
            ''
        ) AS IDPEL,
        WAKTU_PERIKSA,
        NAMA_PETUGAS
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
      AND WAKTU_PERIKSA < TIMESTAMP '2026-07-01'
      AND IDPEL IS NOT NULL
)

SELECT COUNT(*)
FROM inspection_by_idpel
"""

print(c.execute(q).fetchone())

print(
    c.execute("""
    WITH inspection_by_idpel AS (
        SELECT DISTINCT
            REGEXP_REPLACE(
                TRIM(CAST(IDPEL AS VARCHAR)),
                '\\.0$',
                ''
            ) AS IDPEL
        FROM fact_pengecekan
        WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
        AND WAKTU_PERIKSA < TIMESTAMP '2026-07-01'
        AND IDPEL IS NOT NULL
    )
    SELECT *
    FROM inspection_by_idpel
    LIMIT 5
    """).fetchall()
)

c.close()
