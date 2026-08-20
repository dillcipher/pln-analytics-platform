from app.infrastructure.duckdb.connection import get_connection

c = get_connection()

print(
    c.execute(
        '''
        SELECT 
            typeof(IDPEL),
            typeof(LOCATION_CODE)
        FROM fact_pengecekan, fact_anev
        LIMIT 1
        '''
    ).fetchall()
)

c.close()
