import api from "./api";

/**
 * Suspect Analytics API
 *
 * Backend yang pernah dipakai di project ini mengembalikan beberapa bentuk
 * response (raw array/object maupun dibungkus { success, data }).
 * Semua normalisasi dilakukan di sini supaya page tidak perlu menebak shape.
 */

export interface SuspectMonth {
    month_key: string;
    label: string;
}

export interface SuspectClassification {
    classification: string;
    total: number;
}

export interface SuspectUnitapSummary {
    unitap: string;
    total: number;
}

export interface SuspectTariffSummary {
    tariff: string;
    total: number;
}

export interface SuspectAnevSummary {
    total_locations: number;
    total_classifications: number;
    classification: SuspectClassification[];
    unitap: SuspectUnitapSummary[];
    tariff: SuspectTariffSummary[];
}

export interface SuspectRepeatFrequency {
    repeat_count: number;
    locations: number;
}

export interface SuspectRepeatBySuspect {
    classification: string;
    total_customers: number;
    repeat_customers: number;
    repeat_occurrences: number;
}

export interface SuspectRepeatSummary {
    total_customers: number;
    repeat_customers: number;
    repeat_occurrences: number;
    repeat_rate_pct: number;
    frequency: SuspectRepeatFrequency[];
    by_suspect: SuspectRepeatBySuspect[];
}

export interface SuspectAnalyticsData {
    anev: SuspectAnevSummary;
    pra_monthly: SuspectAnevSummary;
    classification: SuspectClassification[];
    pasca_repeat: SuspectRepeatSummary;
    repeat_cases: Array<{
        label: string;
        value: number;
    }>;
}

export interface SuspectAnalyticsResponse {
    success: boolean;
    month: string;
    data: SuspectAnalyticsData;
}

export interface SuspectDetailResponse {
    items: Array<Record<string, unknown>>;
    total_rows: number;
    page: number;
    page_size: number;
    total_pages: number;
}

/* ============================================================
 * INSPECTION STATUS
 * ============================================================ */

export type SuspectInspectionStatus =
    | "SUDAH_PERIKSA"
    | "BELUM_PERIKSA";

/* ============================================================
 * MAP POINT
 * ============================================================ */

export interface SuspectMapPoint {
    location_code: string;

    idpel?: string | null;

    location_name?: string | null;

    unitupi?: string | null;

    unitap?: string | null;

    unitup?: string | null;

    tariff?: string | null;

    power?: number | null;

    suspect_name?: string | null;

    latitude: number;

    longitude: number;

    coordinate_source?:
        | "customer_location"
        | "pengecekan"
        | null;

    inspection_status?:
        | SuspectInspectionStatus
        | null;

    waktu_periksa?: string | null;

    nama_petugas?: string | null;

    catatan?: string | null;

    tindaklanjut_pemeriksaan?: string | null;
}

/* ============================================================
 * MAP DATA
 * ============================================================ */

export interface SuspectMapData {
    total_locations: number;

    matched_idpel: number;

    mapped_locations: number;

    unmapped_locations: number;

    points: SuspectMapPoint[];
}

export interface SuspectMapResponse {
    success: boolean;

    month: string;

    data: SuspectMapData;
}

/* ============================================================
 * QUERY FILTERS
 * ============================================================ */

export interface SuspectQueryFilters {
    unitupi?: string;

    unitap?: string;

    unitup?: string;

    tariff?: string;

    suspect_name?: string;

    repeat_count?: number;

    inspection_status?:
        | SuspectInspectionStatus;

    search?: string;
}

/* ============================================================
 * MONTH NORMALIZATION
 * ============================================================ */

function normalizeMonth(
    item: unknown,
): SuspectMonth | null {
    if (
        !item ||
        typeof item !== "object"
    ) {
        return null;
    }

    const row =
        item as Record<
            string,
            unknown
        >;

    const monthKey = String(
        row.month_key ??
            row.month ??
            row.MONTH ??
            row.MONTH_KEY ??
            "",
    ).trim();

    if (!monthKey) {
        return null;
    }

    const label = String(
        row.label ??
            row.month_label ??
            row.month_name ??
            row.LABEL ??
            monthKey,
    ).trim();

    return {
        month_key: monthKey,

        label:
            label ||
            monthKey,
    };
}

function normalizeMonthsPayload(
    payload: unknown,
): SuspectMonth[] {
    if (
        Array.isArray(
            payload,
        )
    ) {
        return payload
            .map(
                normalizeMonth,
            )
            .filter(
                (
                    item,
                ): item is SuspectMonth =>
                    item !== null,
            );
    }

    if (
        payload &&
        typeof payload ===
            "object"
    ) {
        const row =
            payload as Record<
                string,
                unknown
            >;

        const candidates = [
            row.months,

            row.items,

            row.results,

            row.data,
        ];

        for (
            const candidate of candidates
        ) {
            if (
                Array.isArray(
                    candidate,
                )
            ) {
                return candidate
                    .map(
                        normalizeMonth,
                    )
                    .filter(
                        (
                            item,
                        ): item is SuspectMonth =>
                            item !==
                            null,
                    );
            }
        }
    }

    return [];
}

/* ============================================================
 * ANALYTICS NORMALIZATION
 * ============================================================ */

function emptyAnevSummary(): SuspectAnevSummary {
    return {
        total_locations: 0,

        total_classifications: 0,

        classification: [],

        unitap: [],

        tariff: [],
    };
}

function normalizeAnalyticsData(
    payload: unknown,
): SuspectAnalyticsData {
    const raw =
        payload &&
        typeof payload ===
            "object"
            ? (payload as Record<
                  string,
                  unknown
              >)
            : {};

    const anev =
        raw.anev &&
        typeof raw.anev ===
            "object"
            ? (raw.anev as Record<
                  string,
                  unknown
              >)
            : {};

    const pra =
        raw.pra_monthly &&
        typeof raw.pra_monthly ===
            "object"
            ? (raw.pra_monthly as Record<
                  string,
                  unknown
              >)
            : {};

    const repeat =
        raw.pasca_repeat &&
        typeof raw.pasca_repeat ===
            "object"
            ? (raw.pasca_repeat as Record<
                  string,
                  unknown
              >)
            : {};

    return {
        anev: {
            ...emptyAnevSummary(),

            ...anev,

            classification:
                Array.isArray(
                    anev.classification,
                )
                    ? (anev.classification as SuspectClassification[])
                    : [],

            unitap:
                Array.isArray(
                    anev.unitap,
                )
                    ? (anev.unitap as SuspectUnitapSummary[])
                    : [],

            tariff:
                Array.isArray(
                    anev.tariff,
                )
                    ? (anev.tariff as SuspectTariffSummary[])
                    : [],
        },

        pra_monthly: {
            ...emptyAnevSummary(),

            ...pra,

            classification:
                Array.isArray(
                    pra.classification,
                )
                    ? (pra.classification as SuspectClassification[])
                    : [],

            unitap:
                Array.isArray(
                    pra.unitap,
                )
                    ? (pra.unitap as SuspectUnitapSummary[])
                    : [],

            tariff:
                Array.isArray(
                    pra.tariff,
                )
                    ? (pra.tariff as SuspectTariffSummary[])
                    : [],
        },

        classification:
            Array.isArray(
                raw.classification,
            )
                ? (raw.classification as SuspectClassification[])
                : [],

        pasca_repeat: {
            total_customers:
                Number(
                    repeat.total_customers ??
                        0,
                ),

            repeat_customers:
                Number(
                    repeat.repeat_customers ??
                        0,
                ),

            repeat_occurrences:
                Number(
                    repeat.repeat_occurrences ??
                        0,
                ),

            repeat_rate_pct:
                Number(
                    repeat.repeat_rate_pct ??
                        0,
                ),

            frequency:
                Array.isArray(
                    repeat.frequency,
                )
                    ? (repeat.frequency as SuspectRepeatFrequency[])
                    : [],

            by_suspect:
                Array.isArray(
                    repeat.by_suspect,
                )
                    ? (repeat.by_suspect as SuspectRepeatBySuspect[])
                    : [],
        },

        repeat_cases:
            Array.isArray(
                raw.repeat_cases,
            )
                ? (raw.repeat_cases as Array<{
                      label: string;
                      value: number;
                  }>)
                : [],
    };
}

function normalizeAnalyticsResponse(
    payload: unknown,

    month: string,
): SuspectAnalyticsResponse {
    const outer =
        payload &&
        typeof payload ===
            "object"
            ? (payload as Record<
                  string,
                  unknown
              >)
            : {};

    const nested =
        outer.data &&
        typeof outer.data ===
            "object"
            ? outer.data
            : payload;

    return {
        success:
            typeof outer.success ===
            "boolean"
                ? outer.success
                : true,

        month: String(
            outer.month ??
                month,
        ),

        data:
            normalizeAnalyticsData(
                nested,
            ),
    };
}

/* ============================================================
 * MAP RESPONSE NORMALIZATION
 * ============================================================ */

function normalizeMapResponse(
    payload: unknown,

    month: string,
): SuspectMapResponse {
    const isRecord = (
        value: unknown,
    ): value is Record<
        string,
        unknown
    > =>
        !!value &&
        typeof value ===
            "object" &&
        !Array.isArray(value);

    const isPointArray = (
        value: unknown,
    ): value is SuspectMapPoint[] =>
        Array.isArray(value) &&
        value.some(
            (item) =>
                isRecord(item) &&
                (
                    item.latitude !==
                        undefined ||
                    item.LATITUDE !==
                        undefined
                ) &&
                (
                    item.longitude !==
                        undefined ||
                    item.LONGITUDE !==
                        undefined
                ),
        );

    const toPoint = (
        item: unknown,
    ): SuspectMapPoint | null => {
        if (
            !isRecord(item)
        ) {
            return null;
        }

        const latitude =
            Number(
                item.latitude ??
                    item.LATITUDE,
            );

        const longitude =
            Number(
                item.longitude ??
                    item.LONGITUDE,
            );

        if (
            !Number.isFinite(
                latitude,
            ) ||
            !Number.isFinite(
                longitude,
            )
        ) {
            return null;
        }

        return {
            location_code:
                String(
                    item.location_code ??
                        item.LOCATION_CODE ??
                        "",
                ),

            idpel:
                item.idpel ==
                null
                    ? item.IDPEL ==
                      null
                        ? null
                        : String(
                              item.IDPEL,
                          )
                    : String(
                          item.idpel,
                      ),

            location_name:
                item.location_name ==
                null
                    ? item.LOCATION_NAME ==
                      null
                        ? null
                        : String(
                              item.LOCATION_NAME,
                          )
                    : String(
                          item.location_name,
                      ),

            unitupi:
                item.unitupi ==
                null
                    ? item.UNITUPI ==
                      null
                        ? null
                        : String(
                              item.UNITUPI,
                          )
                    : String(
                          item.unitupi,
                      ),

            unitap:
                item.unitap ==
                null
                    ? item.UNITAP ==
                      null
                        ? null
                        : String(
                              item.UNITAP,
                          )
                    : String(
                          item.unitap,
                      ),

            unitup:
                item.unitup ==
                null
                    ? item.UNITUP ==
                      null
                        ? null
                        : String(
                              item.UNITUP,
                          )
                    : String(
                          item.unitup,
                      ),

            tariff:
                item.tariff ==
                null
                    ? item.TARIFF ==
                      null
                        ? null
                        : String(
                              item.TARIFF,
                          )
                    : String(
                          item.tariff,
                      ),

            power:
                item.power ==
                null
                    ? item.POWER ==
                      null
                        ? null
                        : Number(
                              item.POWER,
                          )
                    : Number(
                          item.power,
                      ),

            suspect_name:
                item.suspect_name ==
                null
                    ? item.SUSPECT_NAME ==
                      null
                        ? null
                        : String(
                              item.SUSPECT_NAME,
                          )
                    : String(
                          item.suspect_name,
                      ),

            latitude,

            longitude,

            coordinate_source:
                item.coordinate_source ===
                    "pengecekan" ||
                item.COORDINATE_SOURCE ===
                    "pengecekan"
                    ? "pengecekan"
                    : "customer_location",

            inspection_status:
                item.inspection_status ===
                    "SUDAH_PERIKSA" ||
                item.INSPECTION_STATUS ===
                    "SUDAH_PERIKSA"
                    ? "SUDAH_PERIKSA"
                    : item.inspection_status ===
                          "BELUM_PERIKSA" ||
                      item.INSPECTION_STATUS ===
                          "BELUM_PERIKSA"
                    ? "BELUM_PERIKSA"
                    : null,

            waktu_periksa:
                item.waktu_periksa ==
                null
                    ? item.WAKTU_PERIKSA ==
                      null
                        ? null
                        : String(
                              item.WAKTU_PERIKSA,
                          )
                    : String(
                          item.waktu_periksa,
                      ),

            nama_petugas:
                item.nama_petugas ==
                null
                    ? item.NAMA_PETUGAS ==
                      null
                        ? null
                        : String(
                              item.NAMA_PETUGAS,
                          )
                    : String(
                          item.nama_petugas,
                      ),

            catatan:
                item.catatan ==
                null
                    ? item.CATATAN ==
                      null
                        ? null
                        : String(
                              item.CATATAN,
                          )
                    : String(
                          item.catatan,
                      ),

            tindaklanjut_pemeriksaan:
                item.tindaklanjut_pemeriksaan ==
                null
                    ? item.TINDAKLANJUT_PEMERIKSAAN ==
                      null
                        ? null
                        : String(
                              item.TINDAKLANJUT_PEMERIKSAAN,
                          )
                    : String(
                          item.tindaklanjut_pemeriksaan,
                      ),
        };
    };

    const search = (
        value: unknown,

        depth = 0,
    ): {
        meta: Record<
            string,
            unknown
        >;

        points: SuspectMapPoint[];
    } | null => {
        if (
            depth > 5 ||
            !value ||
            typeof value !==
                "object"
        ) {
            return null;
        }

        if (
            Array.isArray(
                value,
            )
        ) {
            if (
                isPointArray(
                    value,
                )
            ) {
                return {
                    meta: {},

                    points: value
                        .map(
                            toPoint,
                        )
                        .filter(
                            (
                                point,
                            ): point is SuspectMapPoint =>
                                point !==
                                null,
                        ),
                };
            }

            return null;
        }

        const row =
            value as Record<
                string,
                unknown
            >;

        const candidatePoints = [
            row.points,

            row.items,

            row.results,

            row.locations,
        ];

        for (
            const candidate of candidatePoints
        ) {
            if (
                isPointArray(
                    candidate,
                )
            ) {
                return {
                    meta: row,

                    points:
                        candidate
                            .map(
                                toPoint,
                            )
                            .filter(
                                (
                                    point,
                                ): point is SuspectMapPoint =>
                                    point !==
                                    null,
                            ),
                };
            }
        }

        for (
            const key of [
                "data",
                "result",
                "payload",
            ]
        ) {
            const nested =
                row[key];

            const found =
                search(
                    nested,
                    depth + 1,
                );

            if (found) {
                return {
                    meta: {
                        ...row,

                        ...found.meta,
                    },

                    points:
                        found.points,
                };
            }
        }

        return null;
    };

    const outer =
        isRecord(payload)
            ? payload
            : {};

    const found =
        search(payload);

    const meta =
        found?.meta ??
        outer;

    const points =
        found?.points ??
        [];

    return {
        success:
            typeof outer.success ===
            "boolean"
                ? outer.success
                : true,

        month: String(
            outer.month ??
                month,
        ),

        data: {
            total_locations:
                Number(
                    meta.total_locations ??
                        meta.totalLocations ??
                        0,
                ),

            matched_idpel:
                Number(
                    meta.matched_idpel ??
                        meta.matchedIdpel ??
                        0,
                ),

            mapped_locations:
                Number(
                    meta.mapped_locations ??
                        meta.mappedLocations ??
                        points.length,
                ),

            unmapped_locations:
                Number(
                    meta.unmapped_locations ??
                        meta.unmappedLocations ??
                        0,
                ),

            points,
        },
    };
}

/* ============================================================
 * MONTHS
 * ============================================================ */

export async function getSuspectMonths(): Promise<
    SuspectMonth[]
> {
    const response =
        await api.get<unknown>(
            "/suspect/months",
        );

    return normalizeMonthsPayload(
        response.data,
    ).sort(
        (a, b) =>
            a.month_key.localeCompare(
                b.month_key,
            ),
    );
}

/* ============================================================
 * ANALYTICS
 * ============================================================ */

export async function getSuspectAnalytics(
    month: string,

    filters?: SuspectQueryFilters,
): Promise<SuspectAnalyticsResponse> {
    const params: Record<
        string,
        string | number
    > = {
        month,
    };

    if (
        filters?.unitupi
    ) {
        params.unitupi =
            filters.unitupi;
    }

    if (
        filters?.unitap
    ) {
        params.unitap =
            filters.unitap;
    }

    if (
        filters?.unitup
    ) {
        params.unitup =
            filters.unitup;
    }

    if (
        filters?.tariff
    ) {
        params.tariff =
            filters.tariff;
    }

    if (
        filters?.suspect_name
    ) {
        params.suspect_name =
            filters.suspect_name;
    }

    if (
        filters?.repeat_count
    ) {
        params.repeat_count =
            filters.repeat_count;
    }

    if (
        filters?.search
    ) {
        params.search_customer =
            filters.search;
    }

    const response =
        await api.get<unknown>(
            "/suspect/analytics",
            {
                params,
            },
        );

    return normalizeAnalyticsResponse(
        response.data,
        month,
    );
}

/* ============================================================
 * DETAIL
 * ============================================================ */

export async function getSuspectDetail(
    params: {
        month: string;
        unitupi?: string;
        unitap?: string;
        unitup?: string;
        tariff?: string;
        suspect_name?: string;
        location_code?: string;
        search_customer?: string;
        repeat_count?: number;
        inspection_status?: SuspectInspectionStatus;
        page?: number;
        page_size?: number;
    },
): Promise<SuspectDetailResponse> {
    /*
     * IMPORTANT:
     * Backend /api/v1/suspect/detail currently returns the detail object
     * DIRECTLY:
     *
     * {
     *   "items": [...],
     *   "total_rows": 494676,
     *   "page": 1,
     *   "page_size": 5,
     *   "total_pages": 98936
     * }
     *
     * Some older endpoints / api clients may instead return:
     *
     * {
     *   "success": true,
     *   "data": {
     *      "items": [...],
     *      ...
     *   }
     * }
     *
     * This function deliberately supports BOTH forms, and also supports
     * an axios instance whose interceptor has already unwrapped response.data.
     */

    const response = await api.get<unknown>(
        "/suspect/detail",
        {
            params,
        },
    );

    /*
     * Normal axios response:
     *     response.data = backend payload
     *
     * If app/api.ts has an interceptor that returns response.data directly:
     *     response itself = backend payload
     *
     * Support both so the detail page never depends on the axios
     * interceptor implementation.
     */
    // `api.get()` returns an AxiosResponse, so the backend payload is
    // always available at `response.data`. The API client is typed as
    // Axios, therefore do not cast AxiosResponse itself to Record.
    const payload: unknown = response.data;

    const isRecord = (
        value: unknown,
    ): value is Record<string, unknown> =>
        !!value &&
        typeof value === "object" &&
        !Array.isArray(value);

    /*
     * Resolve the actual detail object.
     *
     * Supported:
     * 1. raw backend response
     * 2. { success, data: rawResponse }
     * 3. { data: { data: rawResponse } }
     *
     * We only unwrap "data" when the current object does NOT itself
     * look like a detail response. This prevents accidentally losing
     * the direct backend payload.
     */
    const looksLikeDetailResponse = (
        value: unknown,
    ): value is Record<string, unknown> => {
        if (!isRecord(value)) {
            return false;
        }

        return (
            "items" in value ||
            "total_rows" in value ||
            "total_pages" in value ||
            "page_size" in value
        );
    };

    let current: unknown = payload;

    for (let depth = 0; depth < 5; depth += 1) {
        if (looksLikeDetailResponse(current)) {
            break;
        }

        if (!isRecord(current)) {
            break;
        }

        if (
            current.data !== undefined &&
            current.data !== current
        ) {
            current = current.data;
            continue;
        }

        if (
            current.result !== undefined &&
            current.result !== current
        ) {
            current = current.result;
            continue;
        }

        if (
            current.payload !== undefined &&
            current.payload !== current
        ) {
            current = current.payload;
            continue;
        }

        break;
    }

    const result: Record<string, unknown> =
        isRecord(current)
            ? current
            : {};

    /*
     * Normalize the row collection.
     *
     * The backend currently returns `items`.
     * `results`, `rows`, and `data` are accepted for compatibility
     * with older implementations.
     */
    let items: Array<Record<string, unknown>> = [];

    const rawItems =
        result.items ??
        result.results ??
        result.rows;

    if (Array.isArray(rawItems)) {
        items = rawItems.filter(
            (
                item,
            ): item is Record<string, unknown> =>
                !!item &&
                typeof item === "object" &&
                !Array.isArray(item),
        );
    }

    /*
     * Numeric metadata must remain valid numbers even when an older
     * backend serializes them as strings.
     */
    const page =
        Number(
            result.page ??
                params.page ??
                1,
        ) || 1;

    const pageSize =
        Number(
            result.page_size ??
                result.pageSize ??
                params.page_size ??
                50,
        ) || 50;

    const totalRows =
        Number(
            result.total_rows ??
                result.totalRows ??
                0,
        ) || 0;

    const calculatedTotalPages =
        totalRows > 0 && pageSize > 0
            ? Math.ceil(
                  totalRows / pageSize,
              )
            : 0;

    const totalPages =
        Number(
            result.total_pages ??
                result.totalPages ??
                calculatedTotalPages,
        ) ||
        calculatedTotalPages ||
        1;

    return {
        items,
        total_rows: totalRows,
        page,
        page_size: pageSize,
        total_pages: totalPages,
    };
}

/* ============================================================
 * MAP
 * ============================================================ */

export async function getSuspectMap(
    month: string,

    filters?: SuspectQueryFilters,

    limit = 100_000,
): Promise<SuspectMapResponse> {
    const params: Record<
        string,
        string | number
    > = {
        month,

        limit,
    };

    if (
        filters?.unitupi
    ) {
        params.unitupi =
            filters.unitupi;
    }

    if (
        filters?.unitap
    ) {
        params.unitap =
            filters.unitap;
    }

    if (
        filters?.unitup
    ) {
        params.unitup =
            filters.unitup;
    }

    if (
        filters?.tariff
    ) {
        params.tariff =
            filters.tariff;
    }

    if (
        filters?.suspect_name
    ) {
        params.suspect_name =
            filters.suspect_name;
    }

    if (
        filters?.repeat_count
    ) {
        params.repeat_count =
            filters.repeat_count;
    }

    if (
        filters?.inspection_status
    ) {
        params.inspection_status =
            filters.inspection_status;
    }

    if (
        filters?.search
    ) {
        params.search =
            filters.search;
    }

    const response =
        await api.get<unknown>(
            "/suspect/map",
            {
                params,
            },
        );

    return normalizeMapResponse(
        response.data,

        month,
    );
}