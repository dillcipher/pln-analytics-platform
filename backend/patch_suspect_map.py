from pathlib import Path

path = Path(r".\app\infrastructure\duckdb\suspect_repository.py")

text = path.read_text(encoding="utf-8")

start = text.index("    def get_map_points(")

# get next class-level method
rest = text[start + 4:]
next_def = rest.find("\n    def ")
if next_def == -1:
    end = len(text)
else:
    end = start + 4 + next_def

new_method = r'''    def get_map_points(
        self,
        month_key: str,
        search: str | None = None,
        unitupi: str | None = None,
        unitap: str | None = None,
        unitup: str | None = None,
        tariff: str | None = None,
        suspect_name: str | None = None,
        repeat_count: int | None = None,
        limit: int = 100_000,
    ) -> dict[str, Any]:

        empty = {
            "total_locations": 0,
            "matched_idpel": 0,
            "mapped_locations": 0,
            "unmapped_locations": 0,
            "points": [],
        }

        if not dataset_exists("fact_anev"):
            return empty

        if not (
            dataset_exists("fact_customer_location")
            or dataset_exists("fact_pengecekan")
        ):
            return empty

        conn = get_connection()

        try:
            safe_limit = max(1, min(int(limit), 100_000))

            customer_location_source = (
                "fact_customer_location"
                if dataset_exists("fact_customer_location")
                else """(
                    SELECT
                        CAST(NULL AS VARCHAR) AS IDPEL,
                        CAST(NULL AS DOUBLE) AS KOORDINAT_X,
                        CAST(NULL AS DOUBLE) AS KOORDINAT_Y
                    WHERE FALSE
                )"""
            )

            pengecekan_source = (
                "fact_pengecekan"
                if dataset_exists("fact_pengecekan")
                else """(
                    SELECT
                        CAST(NULL AS VARCHAR) AS IDPEL,
                        CAST(NULL AS DOUBLE) AS LATITUDE,
                        CAST(NULL AS DOUBLE) AS LONGITUDE,
                        CAST(NULL AS TIMESTAMP) AS WAKTU_PERIKSA,
                        CAST(NULL AS VARCHAR) AS NAMA_PETUGAS,
                        CAST(NULL AS VARCHAR) AS CATATAN,
                        CAST(NULL AS VARCHAR) AS TINDAKLANJUT_PEMERIKSAAN
                    WHERE FALSE
                )"""
            )

            normalized_suspect_sql = """
                CASE
                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'ASYMMETRICPOWERBYINSTANT'
                    THEN 'ASYMMETRIC POWER BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'INCORRECTPHASEBYINSTANT'
                    THEN 'INCORRECT PHASE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'OVERCURRENTBYINSTANT'
                    THEN 'OVER CURRENT BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'OVERVOLTAGEBYINSTANT'
                    THEN 'OVER VOLTAGE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'REVERSALBYINSTANT'
                    THEN 'REVERSAL BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'TIMEDIFFERENCE-INSTANT'
                    THEN 'TIME DIFFERENCE - INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'UNBALANCECURRENTBYINSTANT'
                    THEN 'UNBALANCE CURRENT BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'UNDERVOLTAGEBYINSTANT'
                    THEN 'UNDER VOLTAGE BY INSTANT'

                    WHEN REPLACE(
                        REGEXP_REPLACE(
                            TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                            '\\s+', ' ', 'g'
                        ),
                        ' ',
                        ''
                    ) = 'VOLTAGEDIP-INSTANT'
                    THEN 'VOLTAGE DIP - INSTANT'

                    ELSE REGEXP_REPLACE(
                        TRIM(UPPER(CAST(SUSPECT_NAME AS VARCHAR))),
                        '\\s+', ' ', 'g'
                    )
                END
            """

            clauses = [
                "CAST(MONTH AS VARCHAR) = ?",
                "LOCATION_CODE IS NOT NULL",
                "SUSPECT_NAME IS NOT NULL",
            ]

            params: list[Any] = [str(month_key)]

            if unitupi:
                clauses.append("CAST(UNITUPI AS VARCHAR) = ?")
                params.append(str(unitupi))

            if unitap:
                clauses.append("CAST(UNITAP AS VARCHAR) = ?")
                params.append(str(unitap))

            if unitup:
                clauses.append("CAST(UNITUP AS VARCHAR) = ?")
                params.append(str(unitup))

            if tariff:
                clauses.append("CAST(TARIFF AS VARCHAR) = ?")
                params.append(str(tariff))

            if suspect_name:
                clauses.append(f"{normalized_suspect_sql} = ?")
                params.append(
                    " ".join(str(suspect_name).strip().upper().split())
                )

            if search:
                search_value = f"%{search.strip()}%"
                clauses.append(
                    "(CAST(LOCATION_CODE AS VARCHAR) ILIKE ? "
                    "OR CAST(LOCATION_NAME AS VARCHAR) ILIKE ?)"
                )
                params.extend([search_value, search_value])

            repeat_cte = ""
            repeat_join = ""
            repeat_params: list[Any] = []

            if repeat_count is not None:
                repeat_cte = """
                    , repeat_frequency AS (
                        SELECT
                            CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE,
                            COUNT(DISTINCT CAST(MONTH AS VARCHAR)) AS REPEAT_COUNT
                        FROM fact_anev
                        WHERE LOCATION_CODE IS NOT NULL
                          AND MONTH IS NOT NULL
                          AND CAST(MONTH AS VARCHAR) <= ?
                        GROUP BY LOCATION_CODE
                    )
                """

                repeat_join = """
                    INNER JOIN repeat_frequency rf
                        ON rf.LOCATION_CODE = s.LOCATION_CODE
                       AND rf.REPEAT_COUNT = ?
                """

                repeat_params = [
                    str(month_key),
                    int(repeat_count),
                ]

            sql = f"""
                WITH suspect_rows AS (
                    SELECT
                        CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE,
                        CAST(LOCATION_CODE AS VARCHAR) AS IDPEL,
                        CAST(LOCATION_NAME AS VARCHAR) AS LOCATION_NAME,
                        CAST(UNITUPI AS VARCHAR) AS UNITUPI,
                        CAST(UNITAP AS VARCHAR) AS UNITAP,
                        CAST(UNITUP AS VARCHAR) AS UNITUP,
                        CAST(TARIFF AS VARCHAR) AS TARIFF,
                        TRY_CAST(POWER AS DOUBLE) AS POWER,
                        {normalized_suspect_sql} AS SUSPECT_NAME
                    FROM fact_anev
                    WHERE {' AND '.join(clauses)}
                ),

                suspect_locations AS (
                    SELECT
                        LOCATION_CODE,
                        ANY_VALUE(IDPEL) AS IDPEL,
                        ANY_VALUE(LOCATION_NAME) AS LOCATION_NAME,
                        ANY_VALUE(UNITUPI) AS UNITUPI,
                        ANY_VALUE(UNITAP) AS UNITAP,
                        ANY_VALUE(UNITUP) AS UNITUP,
                        ANY_VALUE(TARIFF) AS TARIFF,
                        ANY_VALUE(POWER) AS POWER,
                        STRING_AGG(
                            DISTINCT SUSPECT_NAME,
                            ', ' ORDER BY SUSPECT_NAME
                        ) AS SUSPECT_NAME
                    FROM suspect_rows
                    GROUP BY LOCATION_CODE
                )

                {repeat_cte}

                , customer_location_raw AS (
                    SELECT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL,
                        TRY_CAST(KOORDINAT_X AS DOUBLE) AS RAW_X,
                        TRY_CAST(KOORDINAT_Y AS DOUBLE) AS RAW_Y
                    FROM {customer_location_source}
                    WHERE IDPEL IS NOT NULL
                ),

                customer_location_normalized AS (
                    SELECT
                        IDPEL,

                        CASE
                            WHEN RAW_X BETWEEN -6.6 AND -3.7
                             AND RAW_Y BETWEEN 103.0 AND 106.5
                            THEN RAW_X

                            WHEN RAW_X BETWEEN 103.0 AND 106.5
                             AND RAW_Y BETWEEN -6.6 AND -3.7
                            THEN RAW_Y

                            ELSE NULL
                        END AS LATITUDE,

                        CASE
                            WHEN RAW_X BETWEEN -6.6 AND -3.7
                             AND RAW_Y BETWEEN 103.0 AND 106.5
                            THEN RAW_Y

                            WHEN RAW_X BETWEEN 103.0 AND 106.5
                             AND RAW_Y BETWEEN -6.6 AND -3.7
                            THEN RAW_X

                            ELSE NULL
                        END AS LONGITUDE

                    FROM customer_location_raw
                ),

                customer_location_by_idpel AS (
                    SELECT
                        IDPEL,
                        LATITUDE,
                        LONGITUDE
                    FROM (
                        SELECT
                            IDPEL,
                            LATITUDE,
                            LONGITUDE,
                            ROW_NUMBER() OVER (
                                PARTITION BY IDPEL
                                ORDER BY
                                    CASE
                                        WHEN LATITUDE IS NOT NULL
                                         AND LONGITUDE IS NOT NULL
                                        THEN 0
                                        ELSE 1
                                    END
                            ) AS RN
                        FROM customer_location_normalized
                        WHERE LATITUDE IS NOT NULL
                          AND LONGITUDE IS NOT NULL
                    ) x
                    WHERE RN = 1
                ),

                pengecekan_raw AS (
                    SELECT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL,

                        TRY_CAST(LATITUDE AS DOUBLE) AS LATITUDE,
                        TRY_CAST(LONGITUDE AS DOUBLE) AS LONGITUDE,

                        WAKTU_PERIKSA,
                        CAST(NAMA_PETUGAS AS VARCHAR) AS NAMA_PETUGAS,
                        CAST(CATATAN AS VARCHAR) AS CATATAN,
                        CAST(
                            TINDAKLANJUT_PEMERIKSAAN
                            AS VARCHAR
                        ) AS TINDAKLANJUT_PEMERIKSAAN

                    FROM {pengecekan_source}

                    WHERE IDPEL IS NOT NULL
                ),

                pengecekan_by_idpel AS (
                    SELECT
                        IDPEL,
                        LATITUDE,
                        LONGITUDE
                    FROM (
                        SELECT
                            IDPEL,
                            LATITUDE,
                            LONGITUDE,
                            ROW_NUMBER() OVER (
                                PARTITION BY IDPEL
                                ORDER BY WAKTU_PERIKSA DESC NULLS LAST
                            ) AS RN
                        FROM pengecekan_raw
                        WHERE LATITUDE BETWEEN -6.6 AND -3.7
                          AND LONGITUDE BETWEEN 103.0 AND 106.5
                    ) x
                    WHERE RN = 1
                ),

                inspection_by_idpel AS (
                    SELECT
                        IDPEL,
                        WAKTU_PERIKSA,
                        NAMA_PETUGAS,
                        CATATAN,
                        TINDAKLANJUT_PEMERIKSAAN
                    FROM (
                        SELECT
                            IDPEL,
                            WAKTU_PERIKSA,
                            NAMA_PETUGAS,
                            CATATAN,
                            TINDAKLANJUT_PEMERIKSAAN,

                            ROW_NUMBER() OVER (
                                PARTITION BY IDPEL
                                ORDER BY WAKTU_PERIKSA DESC NULLS LAST
                            ) AS RN

                        FROM pengecekan_raw

                        WHERE WAKTU_PERIKSA >=
                              TRY_CAST(? || '01' AS DATE)

                          AND WAKTU_PERIKSA <
                              DATE_ADD(
                                  'month',
                                  1,
                                  TRY_CAST(? || '01' AS DATE)
                              )

                          AND WAKTU_PERIKSA IS NOT NULL
                    ) x

                    WHERE RN = 1
                ),

                mapped AS (
                    SELECT
                        s.LOCATION_CODE,
                        s.IDPEL,
                        s.LOCATION_NAME,
                        s.UNITUPI,
                        s.UNITAP,
                        s.UNITUP,
                        s.TARIFF,
                        s.POWER,
                        s.SUSPECT_NAME,

                        CASE
                            WHEN c.LATITUDE IS NOT NULL
                             AND c.LONGITUDE IS NOT NULL
                            THEN c.LATITUDE
                            ELSE p.LATITUDE
                        END AS LATITUDE,

                        CASE
                            WHEN c.LATITUDE IS NOT NULL
                             AND c.LONGITUDE IS NOT NULL
                            THEN c.LONGITUDE
                            ELSE p.LONGITUDE
                        END AS LONGITUDE,

                        CASE
                            WHEN c.LATITUDE IS NOT NULL
                             AND c.LONGITUDE IS NOT NULL
                            THEN 'customer_location'

                            WHEN p.LATITUDE IS NOT NULL
                             AND p.LONGITUDE IS NOT NULL
                            THEN 'pengecekan'

                            ELSE NULL
                        END AS COORDINATE_SOURCE,

                        CASE
                            WHEN i.IDPEL IS NOT NULL
                            THEN 'SUDAH_PERIKSA'
                            ELSE 'BELUM_PERIKSA'
                        END AS INSPECTION_STATUS,

                        i.WAKTU_PERIKSA,
                        i.NAMA_PETUGAS,
                        i.CATATAN,
                        i.TINDAKLANJUT_PEMERIKSAAN

                    FROM suspect_locations s

                    LEFT JOIN customer_location_by_idpel c
                        ON REGEXP_REPLACE(
                            TRIM(s.IDPEL),
                            '\\.0$',
                            ''
                        ) = c.IDPEL

                    LEFT JOIN pengecekan_by_idpel p
                        ON REGEXP_REPLACE(
                            TRIM(s.IDPEL),
                            '\\.0$',
                            ''
                        ) = p.IDPEL

                    LEFT JOIN inspection_by_idpel i
                        ON REGEXP_REPLACE(
                            TRIM(s.IDPEL),
                            '\\.0$',
                            ''
                        ) = i.IDPEL

                    {repeat_join}
                )

                SELECT
                    LOCATION_CODE,
                    IDPEL,
                    LOCATION_NAME,
                    UNITUPI,
                    UNITAP,
                    UNITUP,
                    TARIFF,
                    POWER,
                    SUSPECT_NAME,
                    LATITUDE,
                    LONGITUDE,
                    COORDINATE_SOURCE,
                    INSPECTION_STATUS,
                    WAKTU_PERIKSA,
                    NAMA_PETUGAS,
                    CATATAN,
                    TINDAKLANJUT_PEMERIKSAAN

                FROM mapped

                ORDER BY UNITUP, LOCATION_CODE

                LIMIT ?
            """

            query_params = [
                *params,
                *repeat_params,
                str(month_key),
                str(month_key),
                safe_limit,
            ]

            rows = conn.execute(
                sql,
                query_params,
            ).fetchall()

            points = []

            for row in rows:
                latitude = row[9]
                longitude = row[10]

                if latitude is None or longitude is None:
                    continue

                points.append({
                    "location_code": str(row[0]),
                    "idpel": str(row[1]) if row[1] is not None else None,
                    "location_name": row[2],
                    "unitupi": row[3],
                    "unitap": row[4],
                    "unitup": row[5],
                    "tariff": row[6],
                    "power": row[7],
                    "suspect_name": row[8],

                    "latitude": float(latitude),
                    "longitude": float(longitude),

                    "coordinate_source": row[11],

                    "inspection_status": row[12],

                    "waktu_periksa": (
                        row[13].isoformat()
                        if row[13] is not None
                        else None
                    ),

                    "nama_petugas": row[14],
                    "catatan": row[15],
                    "tindaklanjut_pemeriksaan": row[16],
                })

            # Coverage tetap dihitung berdasarkan populasi lokasi,
            # bukan berdasarkan LIMIT.
            coverage_sql = f"""
                WITH suspect_locations AS (
                    SELECT
                        CAST(LOCATION_CODE AS VARCHAR) AS LOCATION_CODE
                    FROM fact_anev
                    WHERE {' AND '.join(clauses)}
                    GROUP BY LOCATION_CODE
                ),

                customer_location_raw AS (
                    SELECT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL,

                        TRY_CAST(KOORDINAT_X AS DOUBLE) AS RAW_X,
                        TRY_CAST(KOORDINAT_Y AS DOUBLE) AS RAW_Y

                    FROM {customer_location_source}

                    WHERE IDPEL IS NOT NULL
                ),

                customer_location_by_idpel AS (
                    SELECT DISTINCT
                        IDPEL

                    FROM customer_location_raw

                    WHERE (
                        RAW_X BETWEEN -6.6 AND -3.7
                        AND RAW_Y BETWEEN 103.0 AND 106.5
                    )

                    OR (
                        RAW_X BETWEEN 103.0 AND 106.5
                        AND RAW_Y BETWEEN -6.6 AND -3.7
                    )
                ),

                pengecekan_by_idpel AS (
                    SELECT DISTINCT
                        REGEXP_REPLACE(
                            TRIM(CAST(IDPEL AS VARCHAR)),
                            '\\.0$',
                            ''
                        ) AS IDPEL

                    FROM {pengecekan_source}

                    WHERE IDPEL IS NOT NULL
                      AND LATITUDE BETWEEN -6.6 AND -3.7
                      AND LONGITUDE BETWEEN 103.0 AND 106.5
                )

                SELECT
                    COUNT(DISTINCT s.LOCATION_CODE),

                    COUNT(
                        DISTINCT CASE
                            WHEN c.IDPEL IS NOT NULL
                              OR p.IDPEL IS NOT NULL
                            THEN s.LOCATION_CODE
                        END
                    ),

                    COUNT(DISTINCT s.LOCATION_CODE)

                FROM suspect_locations s

                LEFT JOIN customer_location_by_idpel c
                    ON REGEXP_REPLACE(
                        TRIM(s.LOCATION_CODE),
                        '\\.0$',
                        ''
                    ) = c.IDPEL

                LEFT JOIN pengecekan_by_idpel p
                    ON REGEXP_REPLACE(
                        TRIM(s.LOCATION_CODE),
                        '\\.0$',
                        ''
                    ) = p.IDPEL
            """

            coverage = conn.execute(
                coverage_sql,
                params,
            ).fetchone()

            total_locations = int(
                coverage[0] or 0
            ) if coverage else 0

            mapped_locations = int(
                coverage[1] or 0
            ) if coverage else 0

            matched_idpel = int(
                coverage[2] or 0
            ) if coverage else 0

            return {
                "total_locations": total_locations,
                "matched_idpel": matched_idpel,
                "mapped_locations": mapped_locations,
                "unmapped_locations": max(
                    total_locations - mapped_locations,
                    0,
                ),
                "points": points,
            }

        finally:
            conn.close()
'''

text = text[:start] + new_method + text[end:]

path.write_text(text, encoding="utf-8")

print("PATCHED:", path)
