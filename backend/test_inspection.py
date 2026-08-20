from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
SELECT
    CASE
        WHEN p.IDPEL IS NOT NULL THEN 'SUDAH_PERIKSA'
        ELSE 'BELUM_PERIKSA'
    END AS STATUS,
    COUNT(DISTINCT a.LOCATION_CODE) AS JUMLAH
FROM fact_anev a
LEFT JOIN (
    SELECT DISTINCT
        REGEXP_REPLACE(TRIM(CAST(IDPEL AS VARCHAR)), '\.0$', '') AS IDPEL
    FROM fact_pengecekan
    WHERE CAST(MONTH AS VARCHAR) = '202606'
      AND IDPEL IS NOT NULL
      AND WAKTU_PERIKSA IS NOT NULL
) p
ON REGEXP_REPLACE(TRIM(CAST(a.LOCATION_CODE AS VARCHAR)), '\.0$', '') = p.IDPEL
WHERE CAST(a.MONTH AS VARCHAR) = '202606'
  AND a.LOCATION_CODE IS NOT NULL
GROUP BY STATUS
ORDER BY STATUS
"""

print(c.execute(q).fetchall())
c.close()
