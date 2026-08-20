import api from "./api";

export type CustomerType = "prabayar" | "pascabayar";

export interface MonthOption {
    month_key: string;
    label: string;
}

export interface DlpdDashboard {
    total_target: number;
    normal: number;
    temuan: number;
    belum_periksa: number;
    sudah_periksa: number;
    progress_pct: number;
}

export interface DlpdDashboardUlp {
    unitup: string;
    unit_name: string;
    total: number;
    normal: number;
    temuan: number;
    belum_periksa: number;
    total_pemeriksaan: number;
    percentage: number;
    kwh_lt40?: number;
    kwh_zero?: number;
}

export interface DlpdFilters {
    months: string[];
    unitupi: string[];
    unitap: string[];
    unitup: string[];
    status: string[];
    inspection_status: string[];
    dlpd_repeat: string[];
    kendala: string[];
}

export interface DlpdCustomer {
    idpel: string;
    nama: string;
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    tariff?: string;
    daya?: number;
    alamat?: string;
    status: string;
    dlpd_repeat?: string;
    kategori?: string;
    keterangan?: string;
    alasan?: string;
    catatan?: string;
    petugas?: string;
    regu?: string;
    waktu_periksa?: string;

    latitude?: number;
    longitude?: number;
    google_maps_url?: string | null;
}

export interface DlpdCustomerList {
    items: DlpdCustomer[];
    total_rows: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface InspectionHistory {
    waktu_periksa?: string;
    status?: string;
    petugas?: string;
    regu?: string;
    catatan?: string;
    tindak_lanjut?: string;
}

export interface DlpdCustomerDetail {
    customer: DlpdCustomer | null;
    inspection_history: InspectionHistory[];

    latitude?: number | null;
    longitude?: number | null;
    google_maps_url?: string | null;
}

export interface DlpdMapPoint {
    idpel: string;
    nama: string;
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    tariff?: string;
    daya?: number;
    alamat?: string;
    dlpd?: string | null;
    status?: string | null;
    latitude: number;
    longitude: number;
    coordinate_source?: "customer_location" | "pengecekan" | null;
    google_maps_url?: string | null;
}

export interface DlpdMapPointsResponse {
    total: number;
    location_matched: number;
    mapped: number;
    unmapped: number;
    points: DlpdMapPoint[];
}

export interface DlpdQueryFilters {
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    status?: string;
    inspection_status?: string;
    dlpd_repeat?: string;
    kendala?: string;
    search_idpel?: string;
    search_nama?: string;
}

interface Envelope {
    data?: unknown;
    result?: unknown;
    payload?: unknown;
}

function unwrap<T>(payload: unknown): T {
    if (
        payload &&
        typeof payload === "object" &&
        !Array.isArray(payload)
    ) {
        const row = payload as Envelope;

        if (row.data !== undefined) {
            return row.data as T;
        }

        if (row.result !== undefined) {
            return row.result as T;
        }

        if (row.payload !== undefined) {
            return row.payload as T;
        }
    }

    return payload as T;
}

function buildDlpdParams(
    customerType: CustomerType,
    month?: string,
    filters?: DlpdQueryFilters,
) {
    return Object.fromEntries(
        Object.entries({
            customer_type: customerType,
            month,
            unitupi: filters?.unitupi,
            unitap: filters?.unitap,
            unitup: filters?.unitup,
            status: filters?.status,
            inspection_status: filters?.inspection_status,
            dlpd_repeat: filters?.dlpd_repeat,
            kendala: filters?.kendala,
            search_idpel: filters?.search_idpel,
            search_nama: filters?.search_nama,
        }).filter(
            ([, value]) =>
                value !== undefined &&
                value !== null &&
                value !== "",
        ),
    );
}

function normalizeOptionalNumber(
    value: unknown,
): number | undefined {
    if (
        value === undefined ||
        value === null ||
        value === ""
    ) {
        return undefined;
    }

    const numberValue = Number(value);

    return Number.isFinite(numberValue)
        ? numberValue
        : undefined;
}

function normalizeCustomer(
    row: unknown,
): DlpdCustomer | null {
    if (!row || typeof row !== "object") {
        return null;
    }

    const item =
        row as Record<string, unknown>;

    const idpel = String(
        item.idpel ??
            item.IDPEL ??
            "",
    ).trim();

    if (!idpel) {
        return null;
    }

    return {
        idpel,
        nama: String(
            item.nama ??
                item.NAMA ??
                "",
        ),
        unitupi:
            item.unitupi == null
                ? undefined
                : String(item.unitupi),
        unitap:
            item.unitap == null
                ? undefined
                : String(item.unitap),
        unitup:
            item.unitup == null
                ? undefined
                : String(item.unitup),
        tariff:
            item.tariff == null
                ? undefined
                : String(item.tariff),
        daya: normalizeOptionalNumber(
            item.daya,
        ),
        alamat:
            item.alamat == null
                ? undefined
                : String(item.alamat),
        status: String(
            item.status ??
                item.STATUS ??
                "",
        ),
        dlpd_repeat:
            item.dlpd_repeat == null
                ? undefined
                : String(item.dlpd_repeat),
        kategori:
            item.kategori == null
                ? undefined
                : String(item.kategori),
        keterangan:
            item.keterangan == null
                ? undefined
                : String(item.keterangan),
        alasan:
            item.alasan == null
                ? undefined
                : String(item.alasan),
        catatan:
            item.catatan == null
                ? undefined
                : String(item.catatan),
        petugas:
            item.petugas == null
                ? undefined
                : String(item.petugas),
        regu:
            item.regu == null
                ? undefined
                : String(item.regu),
        waktu_periksa:
            item.waktu_periksa == null
                ? undefined
                : String(item.waktu_periksa),
        latitude: normalizeOptionalNumber(
            item.latitude ??
                item.LATITUDE,
        ),
        longitude: normalizeOptionalNumber(
            item.longitude ??
                item.LONGITUDE,
        ),
        google_maps_url:
            item.google_maps_url == null
                ? null
                : String(item.google_maps_url),
    };
}

function normalizeStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return Array.from(
        new Set(
            value
                .map((item) => String(item).trim())
                .filter(Boolean),
        ),
    );
}

export async function getDlpdDashboard(
    customerType: CustomerType,
    month?: string,
    filters?: DlpdQueryFilters,
): Promise<DlpdDashboard> {
    const response = await api.get<unknown>(
        "/dlpd/dashboard",
        {
            params: buildDlpdParams(
                customerType,
                month,
                filters,
            ),
        },
    );

    const data =
        unwrap<Partial<DlpdDashboard>>(
            response.data,
        ) ?? {};

    return {
        total_target: Number(data.total_target ?? 0),
        normal: Number(data.normal ?? 0),
        temuan: Number(data.temuan ?? 0),
        belum_periksa: Number(
            data.belum_periksa ?? 0,
        ),
        sudah_periksa: Number(
            data.sudah_periksa ?? 0,
        ),
        progress_pct: Number(
            data.progress_pct ?? 0,
        ),
    };
}

export async function getDlpdDashboardUlp(
    customerType: CustomerType,
    month?: string,
    filters?: DlpdQueryFilters,
): Promise<DlpdDashboardUlp[]> {
    const response = await api.get<unknown>(
        "/dlpd/dashboard-ulp",
        {
            params: buildDlpdParams(
                customerType,
                month,
                filters,
            ),
        },
    );

    const value = unwrap<unknown>(
        response.data,
    );

    if (!Array.isArray(value)) {
        return [];
    }

    return value.map((row) => {
        const item = row as Record<string, unknown>;

        return {
            unitup: String(
                item.unitup ?? "",
            ),
            unit_name: String(
                item.unit_name ??
                    item.unitup ??
                    "",
            ),
            total: Number(item.total ?? 0),
            normal: Number(item.normal ?? 0),
            temuan: Number(item.temuan ?? 0),
            belum_periksa: Number(
                item.belum_periksa ?? 0,
            ),
            total_pemeriksaan: Number(
                item.total_pemeriksaan ?? 0,
            ),
            percentage: Number(
                item.percentage ?? 0,
            ),
            ...(item.kwh_lt40 !== undefined
                ? {
                      kwh_lt40: Number(
                          item.kwh_lt40,
                      ),
                  }
                : {}),
            ...(item.kwh_zero !== undefined
                ? {
                      kwh_zero: Number(
                          item.kwh_zero,
                      ),
                  }
                : {}),
        };
    });
}

export async function getDlpdFilters(
    customerType: CustomerType,
    month?: string,
): Promise<DlpdFilters> {
    const response = await api.get<unknown>(
        "/dlpd/filters",
        {
            params: {
                customer_type: customerType,
                ...(month ? { month } : {}),
            },
        },
    );

    const raw =
        unwrap<Partial<DlpdFilters>>(
            response.data,
        ) ?? {};

    return {
        months: normalizeStringArray(
            raw.months,
        ),
        unitupi: normalizeStringArray(
            raw.unitupi,
        ),
        unitap: normalizeStringArray(
            raw.unitap,
        ),
        unitup: normalizeStringArray(
            raw.unitup,
        ),
        status: normalizeStringArray(
            raw.status,
        ),
        inspection_status:
            normalizeStringArray(
                raw.inspection_status,
            ),
        dlpd_repeat:
            normalizeStringArray(
                raw.dlpd_repeat,
            ),
        kendala: normalizeStringArray(
            raw.kendala,
        ),
    };
}

export async function getDlpdMonths(
    customerType: CustomerType,
): Promise<MonthOption[]> {
    const response = await api.get<unknown>(
        "/dlpd/months",
        {
            params: {
                customer_type: customerType,
            },
        },
    );

    const value = unwrap<unknown>(
        response.data,
    );

    if (!Array.isArray(value)) {
        return [];
    }

    return value
        .map((row) => {
            if (
                !row ||
                typeof row !== "object"
            ) {
                return null;
            }

            const item =
                row as Record<
                    string,
                    unknown
                >;

            const monthKey = String(
                item.month_key ??
                    item.month ??
                    "",
            ).trim();

            if (!/^\d{6}$/.test(monthKey)) {
                return null;
            }

            return {
                month_key: monthKey,
                label: String(
                    item.label ??
                        item.month_label ??
                        monthKey,
                ).trim(),
            };
        })
        .filter(
            (item): item is MonthOption =>
                item !== null,
        )
        .sort((a, b) =>
            a.month_key.localeCompare(
                b.month_key,
            ),
        );
}

export async function getDlpdCustomers(
    params: Record<string, unknown>,
): Promise<DlpdCustomerList> {
    const normalized =
        Object.fromEntries(
            Object.entries({
                customer_type:
                    params.customer_type ??
                    params.customerType,
                month: params.month,
                page: params.page,
                page_size:
                    params.page_size ??
                    params.pageSize,
                unitupi: params.unitupi,
                unitap: params.unitap,
                unitup: params.unitup,
                status: params.status,
                inspection_status:
                    params.inspection_status,
                dlpd_repeat:
                    params.dlpd_repeat,
                kendala: params.kendala,
                search_idpel:
                    params.search_idpel,
                search_nama:
                    params.search_nama,
            }).filter(
                ([, value]) =>
                    value !== undefined &&
                    value !== null &&
                    value !== "",
            ),
        );

    const response = await api.get<unknown>(
        "/dlpd/customers",
        { params: normalized },
    );

    const raw =
        unwrap<Partial<DlpdCustomerList>>(
            response.data,
        ) ?? {};

    const rawItems = Array.isArray(raw.items)
        ? raw.items
        : [];

    const items = rawItems
        .map(normalizeCustomer)
        .filter(
            (item): item is DlpdCustomer =>
                item !== null,
        );

    return {
        items,
        total_rows: Number(
            raw.total_rows ?? 0,
        ),
        page: Number(
            raw.page ??
                params.page ??
                1,
        ),
        page_size: Number(
            raw.page_size ??
                params.page_size ??
                params.pageSize ??
                50,
        ),
        total_pages: Number(
            raw.total_pages ?? 1,
        ),
    };
}

export async function getDlpdCustomerDetail(
    idpel: string,
    customerType: CustomerType,
    month?: string,
): Promise<DlpdCustomerDetail> {
    const response = await api.get<unknown>(
        `/dlpd/customers/${encodeURIComponent(
            idpel,
        )}`,
        {
            params: {
                customer_type: customerType,
                ...(month ? { month } : {}),
            },
        },
    );

    const raw =
        unwrap<Partial<DlpdCustomerDetail>>(
            response.data,
        ) ?? {};

    const customer =
        normalizeCustomer(raw.customer);

    const customerLatitude =
        normalizeOptionalNumber(
            raw.latitude ??
                customer?.latitude,
        );

    const customerLongitude =
        normalizeOptionalNumber(
            raw.longitude ??
                customer?.longitude,
        );

    const explicitMapsUrl =
        raw.google_maps_url ??
        customer?.google_maps_url ??
        null;

    const googleMapsUrl =
        typeof explicitMapsUrl === "string" &&
        explicitMapsUrl.trim() !== ""
            ? explicitMapsUrl.trim()
            : customer &&
                customerLatitude !== undefined &&
                customerLongitude !== undefined
              ? (
                    "https://www.google.com/maps/search/?api=1&query=" +
                    encodeURIComponent(
                        `${customerLatitude},${customerLongitude}`,
                    )
                )
              : customer
                ? (
                      "https://www.google.com/maps/search/?api=1&query=" +
                      encodeURIComponent(
                          `IDPEL ${customer.idpel}`,
                      )
                  )
                : null;

    return {
        customer: customer
            ? {
                  ...customer,
                  latitude:
                      customerLatitude,
                  longitude:
                      customerLongitude,
                  google_maps_url:
                      googleMapsUrl,
              }
            : null,
        inspection_history:
            Array.isArray(
                raw.inspection_history,
            )
                ? raw.inspection_history.map(
                      (row) => ({
                          waktu_periksa:
                              row?.waktu_periksa,
                          status: row?.status,
                          petugas:
                              row?.petugas,
                          regu: row?.regu,
                          catatan:
                              row?.catatan,
                          tindak_lanjut:
                              row?.tindak_lanjut,
                      }),
                  )
                : [],
        latitude:
            customerLatitude ?? null,
        longitude:
            customerLongitude ?? null,
        google_maps_url:
            googleMapsUrl,
    };
}

export async function exportDlpd(
    format: "csv" | "xlsx",
    params: Record<string, unknown>,
) {
    const response = await api.get(
        `/dlpd/customers/export/${format}`,
        {
            params,
            responseType: "blob",
        },
    );

    return response.data;
}

export async function getDlpdMapPoints(
    customerType: CustomerType,
    month?: string,
    filters?: DlpdQueryFilters,
    limit = 100_000,
): Promise<DlpdMapPointsResponse> {
    const response = await api.get<unknown>(
        "/dlpd/map",
        {
            params: {
                ...buildDlpdParams(
                    customerType,
                    month,
                    filters,
                ),
                limit,
            },
        },
    );

    const raw =
        unwrap<{
            total?: unknown;
            location_matched?: unknown;
            mapped?: unknown;
            unmapped?: unknown;
            points?: unknown;
        }>(response.data) ?? {};

    const rawPoints = Array.isArray(raw.points)
        ? raw.points
        : [];

    const points: DlpdMapPoint[] = [];

    for (const row of rawPoints) {
        if (!row || typeof row !== "object") {
            continue;
        }

        const item = row as unknown as Record<string, unknown>;

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
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude)
        ) {
            continue;
        }

        points.push({
                      idpel: String(
                          item.idpel ??
                              item.IDPEL ??
                              "",
                      ),
                      nama: String(
                          item.nama ??
                              item.NAMA ??
                              "",
                      ),
                      unitupi:
                          item.unitupi == null
                              ? undefined
                              : String(
                                    item.unitupi,
                                ),
                      unitap:
                          item.unitap == null
                              ? undefined
                              : String(
                                    item.unitap,
                                ),
                      unitup:
                          item.unitup == null
                              ? undefined
                              : String(
                                    item.unitup,
                                ),
                      tariff:
                          item.tariff == null
                              ? undefined
                              : String(
                                    item.tariff,
                                ),
                      daya:
                          item.daya == null
                              ? undefined
                              : Number(
                                    item.daya,
                                ),
                      alamat:
                          item.alamat == null
                              ? undefined
                              : String(
                                    item.alamat,
                                ),
                      dlpd:
                          item.dlpd == null
                              ? null
                              : String(
                                    item.dlpd,
                                ),
                      status:
                          item.status == null
                              ? null
                              : String(
                                    item.status,
                                ),
                      latitude,
                      longitude,
                      coordinate_source:
                          item.coordinate_source ===
                              "pengecekan"
                              ? "pengecekan"
                              : item.coordinate_source ===
                                "customer_location"
                              ? "customer_location"
                              : null,
                      google_maps_url:
                          item.google_maps_url == null
                              ? null
                              : String(
                                    item.google_maps_url,
                                ),
        });
    }

    const total = Number(
        raw.total ?? 0,
    );

    const mapped = Number(
        raw.mapped ?? points.length,
    );

    return {
        total,
        location_matched: Number(
            raw.location_matched ?? 0,
        ),
        mapped,
        unmapped: Number(
            raw.unmapped ??
                Math.max(
                    total - mapped,
                    0,
                ),
        ),
        points,
    };
}


/**
 * Get the direct Google Maps destination for one DLPD customer.
 *
 * The backend can return:
 *   { google_maps_url: "..." }
 * or a wrapped equivalent. If the backend does not provide a URL,
 * coordinates are converted into a Google Maps search URL.
 */
export async function getDlpdCustomerMaps(
    idpel: string,
    customerType: CustomerType,
    month?: string,
): Promise<string | null> {
    const normalizedIdpel =
        String(idpel ?? "").trim();

    if (!normalizedIdpel) {
        return null;
    }

    const response = await api.get<unknown>(
        `/dlpd/customers/${encodeURIComponent(
            normalizedIdpel,
        )}/maps`,
        {
            params: {
                customer_type: customerType,
                ...(month ? { month } : {}),
            },
        },
    );

    const raw =
        unwrap<Record<string, unknown>>(
            response.data,
        ) ?? {};

    const explicitUrl =
        raw.google_maps_url ??
        raw.url ??
        null;

    if (
        typeof explicitUrl === "string" &&
        explicitUrl.trim() !== ""
    ) {
        return explicitUrl.trim();
    }

    const latitude =
        normalizeOptionalNumber(
            raw.latitude ??
                raw.LATITUDE,
        );

    const longitude =
        normalizeOptionalNumber(
            raw.longitude ??
                raw.LONGITUDE,
        );

    if (
        latitude !== undefined &&
        longitude !== undefined
    ) {
        return (
            "https://www.google.com/maps/search/?api=1&query=" +
            encodeURIComponent(
                `${latitude},${longitude}`,
            )
        );
    }

    return (
        "https://www.google.com/maps/search/?api=1&query=" +
        encodeURIComponent(
            `IDPEL ${normalizedIdpel}`,
        )
    );
}
