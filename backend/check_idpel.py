from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

rows = c.execute(
    '''
    SELECT 
        IDPEL,
        LENGTH(CAST(IDPEL AS VARCHAR))
    FROM fact_pengecekan
    WHERE WAKTU_PERIKSA >= TIMESTAMP '2026-06-01'
    LIMIT 5
    '''
).fetchall()

for r in rows:
    print(r)

c.close()
