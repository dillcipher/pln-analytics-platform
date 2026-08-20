from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
SELECT
    a.LOCATION_CODE,
    p.IDPEL,
    p.WAKTU_PERIKSA,
    p.NAMA_PETUGAS
FROM fact_anev a
INNER JOIN fact_pengecekan p
ON TRIM(CAST(a.LOCATION_CODE AS VARCHAR))
 =
   TRIM(CAST(p.IDPEL AS VARCHAR))
WHERE CAST(a.MONTH AS VARCHAR)='202606'
AND p.WAKTU_PERIKSA IS NOT NULL
LIMIT 10
"""

rows = c.execute(q).fetchall()

print("MATCH:", len(rows))

for r in rows:
    print(r)

c.close()
