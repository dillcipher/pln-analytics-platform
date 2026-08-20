from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
SELECT
    a.LOCATION_CODE,
    a.LOCATION_NAME,
    p.IDPEL,
    p.WAKTU_PERIKSA,
    p.NAMA_PETUGAS,
    p.TINDAKLANJUT_PEMERIKSAAN,
    p.CATATAN,
    p.LATITUDE,
    p.LONGITUDE
FROM fact_anev a
INNER JOIN fact_pengecekan p
    ON TRIM(CAST(a.LOCATION_CODE AS VARCHAR))
     = TRIM(CAST(p.IDPEL AS VARCHAR))
WHERE CAST(a.MONTH AS VARCHAR) = '202606'
  AND p.WAKTU_PERIKSA >= TIMESTAMP '2026-06-01 00:00:00'
  AND p.WAKTU_PERIKSA <  TIMESTAMP '2026-07-01 00:00:00'
ORDER BY p.WAKTU_PERIKSA DESC
LIMIT 5
"""

for row in c.execute(q).fetchall():
    print(row)

c.close()
