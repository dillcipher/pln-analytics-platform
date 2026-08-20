from app.infrastructure.duckdb.connection import get_connection

c=get_connection()

q="""
WITH inspection AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(IDPEL AS VARCHAR)),
            '\.0$',
            ''
        ) AS IDPEL
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
      AND WAKTU_PERIKSA < TIMESTAMP '2026-07-01'
),

suspect AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(LOCATION_CODE AS VARCHAR)),
            '\.0$',
            ''
        ) AS IDPEL
    FROM fact_anev
    WHERE CAST(MONTH AS VARCHAR)='202606'
)

SELECT
    COUNT(*)
FROM suspect s
JOIN inspection i
ON s.IDPEL=i.IDPEL
"""

print(c.execute(q).fetchone())


q="""
WITH inspection AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(IDPEL AS VARCHAR)),
            '\.0$',
            ''
        ) AS IDPEL
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
      AND WAKTU_PERIKSA < TIMESTAMP '2026-07-01'
)

SELECT *
FROM inspection
WHERE IDPEL='171310403491'
"""

print(c.execute(q).fetchall())

c.close()
