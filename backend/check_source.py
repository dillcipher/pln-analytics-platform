from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

q = """
SELECT
    COUNT(*),
    COUNT(DISTINCT LOCATION_CODE)
FROM fact_anev
WHERE CAST(MONTH AS VARCHAR)='202606'
"""

print("ANE V:")
print(c.execute(q).fetchone())


q = """
SELECT
    COUNT(*),
    COUNT(DISTINCT IDPEL)
FROM fact_pengecekan
WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
AND WAKTU_PERIKSA < TIMESTAMP '2026-07-01'
"""

print("PENGECEKAN:")
print(c.execute(q).fetchone())


q = """
SELECT
    LOCATION_CODE
FROM fact_anev
WHERE CAST(MONTH AS VARCHAR)='202606'
LIMIT 5
"""

print("SAMPLE ANEV:")
print(c.execute(q).fetchall())

c.close()
