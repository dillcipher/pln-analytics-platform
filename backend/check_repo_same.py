from app.infrastructure.duckdb.connection import get_connection, dataset_exists

c = get_connection()

print("exists:", dataset_exists("fact_pengecekan"))

print(
    c.execute(
        '''
        SELECT COUNT(*)
        FROM fact_pengecekan
        WHERE WAKTU_PERIKSA >= DATE '2026-06-01'
        AND WAKTU_PERIKSA < DATE '2026-07-01'
        '''
    ).fetchone()
)

print(
    c.execute(
        '''
        SELECT COUNT(*)
        FROM fact_pengecekan fp
        WHERE REGEXP_REPLACE(
            TRIM(CAST(fp.IDPEL AS VARCHAR)),
            '\\.0$',
            ''
        ) = '171310720558'
        '''
    ).fetchone()
)

c.close()
