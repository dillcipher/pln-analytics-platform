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
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-05-01 00:00:00'
      AND WAKTU_PERIKSA < TIMESTAMP '2026-06-01 00:00:00'
      AND IDPEL IS NOT NULL
),
suspect AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(LOCATION_CODE AS VARCHAR)),
            '\\.0$',
            ''
        ) AS IDPEL
    FROM fact_anev
    WHERE CAST(MONTH AS VARCHAR)='202605'
)
SELECT COUNT(*)
FROM suspect s
INNER JOIN inspection i
ON s.IDPEL=i.IDPEL
"""

print("MEI:", c.execute(q).fetchone())

q2 = """
WITH inspection AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(IDPEL AS VARCHAR)),
            '\\.0$',
            ''
        ) AS IDPEL
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-04-01 00:00:00'
      AND WAKTU_PERIKSA < TIMESTAMP '2026-05-01 00:00:00'
      AND IDPEL IS NOT NULL
),
suspect AS (
    SELECT DISTINCT
        REGEXP_REPLACE(
            TRIM(CAST(LOCATION_CODE AS VARCHAR)),
            '\\.0$',
            ''
        ) AS IDPEL
    FROM fact_anev
    WHERE CAST(MONTH AS VARCHAR)='202604'
)
SELECT COUNT(*)
FROM suspect s
INNER JOIN inspection i
ON s.IDPEL=i.IDPEL
"""

print("APRIL:", c.execute(q2).fetchone())

c.close()
