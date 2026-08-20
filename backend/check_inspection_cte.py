from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
WITH inspection AS (
    SELECT DISTINCT
        TRIM(CAST(IDPEL AS VARCHAR)) AS IDPEL,
        WAKTU_PERIKSA,
        NAMA_PETUGAS,
        CATATAN
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= DATE '2026-06-01'
      AND WAKTU_PERIKSA < DATE '2026-07-01'
      AND WAKTU_PERIKSA IS NOT NULL
)

SELECT
    IDPEL,
    WAKTU_PERIKSA,
    NAMA_PETUGAS
FROM inspection
LIMIT 10
"""

rows = c.execute(q).fetchall()

print("INSPECTION ROW:", len(rows))

for r in rows:
    print(r)

c.close()
