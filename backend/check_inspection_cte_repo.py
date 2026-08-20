from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
WITH inspection_by_idpel AS (
    SELECT
        REGEXP_REPLACE(
            TRIM(CAST(IDPEL AS VARCHAR)),
            '\\.0$',
            ''
        ) AS IDPEL,
        WAKTU_PERIKSA,
        NAMA_PETUGAS
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TRY_CAST('20260601' AS DATE)
      AND WAKTU_PERIKSA < DATE_ADD(
          TRY_CAST('20260601' AS DATE),
          INTERVAL 1 MONTH
      )
)

SELECT COUNT(*)
FROM inspection_by_idpel
"""

print(c.execute(q).fetchone())

c.close()
