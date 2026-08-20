from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
WITH inspection AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(IDPEL AS VARCHAR)),
            '\\.0$',
            ''
        ) AS IDPEL
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
      AND WAKTU_PERIKSA < TIMESTAMP '2026-07-01'
)

SELECT
    COUNT(*) AS MATCH
FROM fact_anev a
INNER JOIN inspection i
ON REGEXP_REPLACE(
       TRIM(CAST(a.LOCATION_CODE AS VARCHAR)),
       '\\.0$',
       ''
   )
   =
   i.IDPEL
WHERE CAST(a.MONTH AS VARCHAR)='202606'
"""

print(c.execute(q).fetchone())

c.close()
