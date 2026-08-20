import "./DlpdCustomerTable.css";

import {
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    getDlpdCustomers,
} from "../../api/dlpd";


/* ==========================================================
 * TYPES
 * ========================================================== */

type CustomerRow = {
    idpel: string;

    nama: string | null;

    unitupi: string | null;

    unitap: string | null;

    unitup: string | null;

    tariff:
        | string
        | number
        | null;

    daya:
        | string
        | number
        | null;

    alamat: string | null;

    status: string | null;

    dlpd_repeat:
        | string
        | number
        | null;

    kategori: string | null;

    keterangan: string | null;

    alasan: string | null;

    catatan: string | null;

    petugas: string | null;

    regu: string | null;

    waktu_periksa: string | null;

    latitude?: number | null;

    longitude?: number | null;

    google_maps_url?: string | null;
};


/* ==========================================================
 * FILTERS
 * ========================================================== */

type CustomerFilters = {

    /*
     * UNIT
     */
    unitup?: string;

    /*
     * STATUS HASIL
     *
     * NORMAL
     * TEMUAN
     */
    status?: string;

    /*
     * STATUS PEMERIKSAAN
     *
     * SUDAH PERIKSA
     * BELUM PERIKSA
     */
    inspection_status?: string;

    /*
     * KENDALA
     */
    dlpd_repeat?: string;

    kendala?: string;
};


/* ==========================================================
 * API RESPONSE
 * ========================================================== */

type CustomerPage = {
    items: CustomerRow[];

    total_rows: number;

    page: number;

    page_size: number;

    total_pages?: number;
};


/* ==========================================================
 * PROPS
 * ========================================================== */

type Props = {
    customerType:
        | "prabayar"
        | "pascabayar";

    month?: string;

    filters?: CustomerFilters;

    /*
     * Backward compatibility.
     *
     * Tetap diterima kalau parent masih
     * mengirim unitup langsung.
     */
    unitup?: string;

    onSelect: (
        idpel: string,
    ) => void;

    selectedIdpel?: string;
};


/* ==========================================================
 * CONSTANTS
 * ========================================================== */

const PAGE_SIZE = 100;


/* ==========================================================
 * HELPERS
 * ========================================================== */

function formatValue(
    value: unknown,
): string {

    if (
        value === null ||
        value === undefined ||
        String(value).trim() === ""
    ) {
        return "-";
    }

    return String(value);
}


function formatNumber(
    value: unknown,
): string {

    if (
        value === null ||
        value === undefined ||
        String(value).trim() === ""
    ) {
        return "-";
    }


    const numeric =
        Number(value);


    if (
        !Number.isFinite(
            numeric,
        )
    ) {
        return String(value);
    }


    return numeric.toLocaleString(
        "id-ID",
    );
}


function normalizeOptionalNumber(
    value: unknown,
): number | null {
    if (
        value === undefined ||
        value === null ||
        String(value).trim() === ""
    ) {
        return null;
    }

    const numeric = Number(value);

    return Number.isFinite(numeric)
        ? numeric
        : null;
}


function normalizeCustomerRow(
    value: unknown,
): CustomerRow | null {
    if (
        !value ||
        typeof value !== "object" ||
        Array.isArray(value)
    ) {
        return null;
    }

    const item =
        value as Record<string, unknown>;

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
        nama:
            item.nama == null
                ? null
                : String(item.nama),
        unitupi:
            item.unitupi == null
                ? null
                : String(item.unitupi),
        unitap:
            item.unitap == null
                ? null
                : String(item.unitap),
        unitup:
            item.unitup == null
                ? null
                : String(item.unitup),
        tariff:
            item.tariff == null
                ? null
                : item.tariff as string | number,
        daya:
            item.daya == null
                ? null
                : item.daya as string | number,
        alamat:
            item.alamat == null
                ? null
                : String(item.alamat),
        status:
            item.status == null
                ? null
                : String(item.status),
        dlpd_repeat:
            item.dlpd_repeat == null
                ? null
                : item.dlpd_repeat as string | number,
        kategori:
            item.kategori == null
                ? null
                : String(item.kategori),
        keterangan:
            item.keterangan == null
                ? null
                : String(item.keterangan),
        alasan:
            item.alasan == null
                ? null
                : String(item.alasan),
        catatan:
            item.catatan == null
                ? null
                : String(item.catatan),
        petugas:
            item.petugas == null
                ? null
                : String(item.petugas),
        regu:
            item.regu == null
                ? null
                : String(item.regu),
        waktu_periksa:
            item.waktu_periksa == null
                ? null
                : String(item.waktu_periksa),
        latitude:
            normalizeOptionalNumber(
                item.latitude ??
                    item.LATITUDE,
            ),
        longitude:
            normalizeOptionalNumber(
                item.longitude ??
                    item.LONGITUDE,
            ),
        google_maps_url:
            item.google_maps_url == null
                ? null
                : String(
                      item.google_maps_url,
                  ),
    };
}


function statusClass(
    status: string | null,
): string {

    const normalized =
        String(
            status ?? "",
        )
            .trim()
            .toLowerCase();


    if (
        normalized === "normal"
    ) {
        return "status-badge status-normal";
    }


    if (
        normalized === "temuan"
    ) {
        return "status-badge status-temuan";
    }


    return "status-badge status-belum";
}


function unwrapCustomerResponse(
    payload: unknown,
): CustomerPage {
    if (
        payload &&
        typeof payload === "object" &&
        !Array.isArray(payload)
    ) {
        const object =
            payload as Record<string, unknown>;

        const candidates: unknown[] = [
            object,
            object.data,
            object.result,
            object.payload,
        ];

        for (const candidate of candidates) {
            if (
                !candidate ||
                typeof candidate !== "object" ||
                Array.isArray(candidate)
            ) {
                continue;
            }

            const value =
                candidate as Record<
                    string,
                    unknown
                >;

            if (!Array.isArray(value.items)) {
                continue;
            }

            const normalizedItems =
                value.items
                    .map(
                        normalizeCustomerRow,
                    )
                    .filter(
                        (
                            item,
                        ): item is CustomerRow =>
                            item !== null,
                    );

            return {
                items:
                    normalizedItems,

                total_rows:
                    Number.isFinite(
                        Number(
                            value.total_rows ??
                                value.total ??
                                value.count ??
                                normalizedItems.length,
                        ),
                    )
                        ? Number(
                              value.total_rows ??
                                  value.total ??
                                  value.count ??
                                  normalizedItems.length,
                          )
                        : normalizedItems.length,

                page: Number(
                    value.page ?? 1,
                ),

                page_size: Number(
                    value.page_size ??
                        PAGE_SIZE,
                ),

                total_pages:
                    value.total_pages != null
                        ? Number(
                              value.total_pages,
                          )
                        : undefined,
            };
        }
    }

    return {
        items: [],
        total_rows: 0,
        page: 1,
        page_size: PAGE_SIZE,
        total_pages: 0,
    };
}


/* ==========================================================
 * COMPONENT
 * ========================================================== */

export default function DlpdCustomerTable({
    customerType,
    month,
    filters,
    unitup,
    onSelect,
    selectedIdpel,
}: Props) {

    /* ======================================================
     * EFFECTIVE FILTERS
     * ====================================================== */

    const effectiveFilters =
        useMemo(
            () => ({

                /*
                 * UNIT
                 */
                unitup:
                    filters?.unitup ??
                    unitup,

                /*
                 * STATUS HASIL
                 */
                status:
                    filters?.status,

                /*
                 * STATUS PEMERIKSAAN
                 */
                inspection_status:
                    filters?.inspection_status,

                dlpd_repeat:
                    filters?.dlpd_repeat,

                /*
                 * KENDALA
                 */
                kendala:
                    filters?.kendala,

            }),
            [
                filters?.unitup,
                filters?.status,
                filters?.inspection_status,
                filters?.dlpd_repeat,
                filters?.kendala,
                unitup,
            ],
        );


    /* ======================================================
     * STATE
     * ====================================================== */

    const [
        rows,
        setRows,
    ] = useState<
        CustomerRow[]
    >([]);


    const [
        page,
        setPage,
    ] = useState(1);


    const [
        totalRows,
        setTotalRows,
    ] = useState(0);


    const [
        loading,
        setLoading,
    ] = useState(false);


    const [
        error,
        setError,
    ] = useState<
        string | null
    >(null);


    /* ======================================================
     * TOTAL PAGES
     * ====================================================== */

    const totalPages =
        Math.max(
            1,
            Math.ceil(
                totalRows /
                    PAGE_SIZE,
            ),
        );


    /* ======================================================
     * RESET WHEN FILTER CHANGES
     * ====================================================== */

    useEffect(() => {

        setPage(1);

        setRows([]);

        setTotalRows(0);

        onSelect("");

    }, [
        customerType,
        month,
        effectiveFilters.unitup,
        effectiveFilters.status,
        effectiveFilters.inspection_status,
        effectiveFilters.dlpd_repeat,
        effectiveFilters.kendala,
    ]);


    /* ======================================================
     * LOAD CUSTOMERS
     * ====================================================== */

    useEffect(() => {

        /*
         * `month` boleh undefined.
         *
         * Undefined berarti "Semua Bulan". Backend DLPD menerima
         * month=None untuk mengambil seluruh periode, jadi request
         * TETAP harus dijalankan.
         */

        let cancelled =
            false;


        const load =
            async () => {

                try {

                    setLoading(
                        true,
                    );

                    setError(
                        null,
                    );


                    const rawResult =
                        await getDlpdCustomers(
                            {
                                customerType,

                                month,

                                page,

                                pageSize:
                                    PAGE_SIZE,

                                /*
                                 * UNIT
                                 */
                                unitup:
                                    effectiveFilters.unitup,

                                /*
                                 * STATUS HASIL
                                 */
                                status:
                                    effectiveFilters.status,

                                /*
                                 * STATUS PEMERIKSAAN
                                 */
                                inspection_status:
                                    effectiveFilters.inspection_status,

                                dlpd_repeat:
                                    effectiveFilters.dlpd_repeat,

                                /*
                                 * KENDALA
                                 */
                                kendala:
                                    effectiveFilters.kendala,
                            },
                        );


                    if (
                        cancelled
                    ) {
                        return;
                    }


                    const result =
                        unwrapCustomerResponse(
                            rawResult,
                        );


                    setRows(
                        result.items,
                    );


                    setTotalRows(
                        result.total_rows,
                    );

                } catch (
                    err
                ) {

                    console.error(
                        "Failed to load DLPD customers:",
                        err,
                    );


                    if (
                        !cancelled
                    ) {

                        setRows(
                            [],
                        );

                        setTotalRows(
                            0,
                        );

                        setError(
                            "Gagal memuat daftar pelanggan.",
                        );
                    }

                } finally {

                    if (
                        !cancelled
                    ) {

                        setLoading(
                            false,
                        );
                    }
                }
            };


        load();


        return () => {
            cancelled = true;
        };

    }, [
        customerType,
        month,
        page,
        effectiveFilters.unitup,
        effectiveFilters.status,
        effectiveFilters.inspection_status,
        effectiveFilters.dlpd_repeat,
        effectiveFilters.kendala,
    ]);


    /* ======================================================
     * PAGINATION
     * ====================================================== */

    const goToPage = (
        nextPage: number,
    ) => {

        if (
            nextPage < 1 ||
            nextPage > totalPages ||
            nextPage === page
        ) {
            return;
        }


        onSelect("");

        setPage(
            nextPage,
        );
    };


    const startRow =
        totalRows === 0
            ? 0
            : (
                  page - 1
              ) *
                  PAGE_SIZE +
              1;


    const endRow =
        Math.min(
            page *
                PAGE_SIZE,
            totalRows,
        );


    /* ======================================================
     * RENDER
     * ====================================================== */

    return (
        <div className="dlpd-customer-table">

            {/* ==================================================
             * TOOLBAR
             * ================================================== */}

            <div className="customer-table-toolbar">

                <div>
                    <div className="customer-table-summary">
                        {loading
                            ? "Memuat pelanggan..."
                            : `${startRow.toLocaleString(
                                  "id-ID",
                              )}–${endRow.toLocaleString(
                                  "id-ID",
                              )} dari ${totalRows.toLocaleString(
                                  "id-ID",
                              )} pelanggan`}
                    </div>

                    {!loading &&
                        rows.length > 0 && (
                            <div
                                style={{
                                    marginTop: 4,
                                    fontSize: 11,
                                    color: "#64748b",
                                }}
                            >
                                Klik salah satu pelanggan
                                untuk membuka detail.
                            </div>
                        )}
                </div>

                {error && (
                    <div className="customer-table-error">
                        {error}
                    </div>
                )}

            </div>


            {/* ==================================================
             * TABLE
             *
             * Layout intentionally follows the Suspect detail
             * table:
             * - dark header
             * - horizontal scrolling
             * - content width follows columns
             * - compact rows
             * - no card-per-customer layout
             * ================================================== */}

            <div
                className="customer-table-scroll"
                style={{
                    overflowX: "auto",
                    overflowY: "auto",
                    maxWidth: "100%",
                }}
            >
                <table
                    className="customer-table"
                    style={{
                        width: "max-content",
                        minWidth: "100%",
                        borderCollapse: "collapse",
                    }}
                >
                    <thead>
                        <tr>

                            <th>IDPEL</th>

                            <th>Nama</th>

                            <th>UNITUPI</th>

                            <th>UNITAP</th>

                            <th>UNITUP</th>

                            <th>Tarif</th>

                            <th>Daya</th>

                            <th>Status</th>

                            <th>Perulangan</th>

                            <th>Kategori</th>

                            <th>Keterangan</th>

                            <th>Petugas</th>

                            <th>Regu</th>

                            <th>Waktu Periksa</th>

                        </tr>
                    </thead>

                    <tbody>

                        {/* ==========================================
                         * LOADING
                         * ========================================== */}

                        {loading && (
                            <tr>
                                <td
                                    colSpan={14}
                                    className="customer-table-empty"
                                >
                                    Memuat data pelanggan...
                                </td>
                            </tr>
                        )}


                        {/* ==========================================
                         * EMPTY
                         * ========================================== */}

                        {!loading &&
                            rows.length === 0 && (
                                <tr>
                                    <td
                                        colSpan={14}
                                        className="customer-table-empty"
                                    >
                                        Tidak ada pelanggan
                                        yang sesuai dengan filter.
                                    </td>
                                </tr>
                            )}


                        {/* ==========================================
                         * ROWS
                         * ========================================== */}

                        {!loading &&
                            rows.map((row) => (
                                <tr
                                    key={row.idpel}
                                    className={
                                        "customer-table-row customer-table-row-clickable" +
                                        (selectedIdpel ===
                                        row.idpel
                                            ? " customer-table-row-selected"
                                            : "")
                                    }
                                    onClick={() =>
                                        onSelect(
                                            row.idpel,
                                        )
                                    }
                                    onKeyDown={(event) => {
                                        if (
                                            event.key ===
                                                "Enter" ||
                                            event.key ===
                                                " "
                                        ) {
                                            event.preventDefault();

                                            onSelect(
                                                row.idpel,
                                            );
                                        }
                                    }}
                                    tabIndex={0}
                                    role="button"
                                    aria-current={
                                        selectedIdpel ===
                                        row.idpel
                                            ? "true"
                                            : undefined
                                    }
                                    aria-label={`Buka detail pelanggan ${row.idpel}`}
                                >

                                    <td
                                        className="idpel-cell"
                                        title={formatValue(
                                            row.idpel,
                                        )}
                                    >
                                        <div
                                            style={{
                                                display: "flex",
                                                alignItems: "center",
                                                gap: 8,
                                            }}
                                        >
                                            <span>
                                                {formatValue(
                                                    row.idpel,
                                                )}
                                            </span>

                                            {selectedIdpel ===
                                                row.idpel && (
                                                <span
                                                    aria-hidden="true"
                                                    style={{
                                                        color:
                                                            "#60a5fa",
                                                        fontSize:
                                                            11,
                                                        fontWeight:
                                                            700,
                                                    }}
                                                >
                                                    ●
                                                </span>
                                            )}

                                            {row.google_maps_url && (
                                                <span
                                                    title={
                                                        row.latitude !=
                                                            null &&
                                                        row.longitude !=
                                                            null
                                                            ? "Lokasi tersedia"
                                                            : "Google Maps tersedia melalui pencarian IDPEL"
                                                    }
                                                    aria-label={
                                                        row.latitude !=
                                                            null &&
                                                        row.longitude !=
                                                            null
                                                            ? "Lokasi tersedia"
                                                            : "Google Maps tersedia"
                                                    }
                                                    style={{
                                                        display:
                                                            "inline-flex",
                                                        alignItems:
                                                            "center",
                                                        justifyContent:
                                                            "center",
                                                        width: 18,
                                                        height: 18,
                                                        borderRadius:
                                                            "50%",
                                                        background:
                                                            "#1d4ed8",
                                                        color:
                                                            "#ffffff",
                                                        fontSize: 10,
                                                        fontWeight: 700,
                                                        flexShrink: 0,
                                                    }}
                                                >
                                                    M
                                                </span>
                                            )}
                                        </div>
                                    </td>


                                    <td
                                        className="name-cell"
                                        title={formatValue(
                                            row.nama,
                                        )}
                                    >
                                        {formatValue(
                                            row.nama,
                                        )}
                                    </td>


                                    <td>
                                        {formatValue(
                                            row.unitupi,
                                        )}
                                    </td>


                                    <td>
                                        {formatValue(
                                            row.unitap,
                                        )}
                                    </td>


                                    <td>
                                        {formatValue(
                                            row.unitup,
                                        )}
                                    </td>


                                    <td>
                                        {formatValue(
                                            row.tariff,
                                        )}
                                    </td>


                                    <td className="numeric-cell">
                                        {row.daya == null ||
                                        String(
                                            row.daya,
                                        ).trim() === ""
                                            ? "-"
                                            : `${formatNumber(
                                                  row.daya,
                                              )} VA`}
                                    </td>


                                    <td>
                                        <span
                                            className={statusClass(
                                                row.status,
                                            )}
                                        >
                                            {formatValue(
                                                row.status,
                                            )}
                                        </span>
                                    </td>


                                    <td className="numeric-cell">
                                        {formatValue(
                                            row.dlpd_repeat,
                                        )}
                                    </td>


                                    <td
                                        className="category-cell"
                                        title={formatValue(
                                            row.kategori,
                                        )}
                                    >
                                        {formatValue(
                                            row.kategori,
                                        )}
                                    </td>


                                    <td
                                        className="description-cell"
                                        title={formatValue(
                                            row.keterangan ??
                                                row.alasan,
                                        )}
                                    >
                                        {formatValue(
                                            row.keterangan ??
                                                row.alasan,
                                        )}
                                    </td>


                                    <td
                                        title={formatValue(
                                            row.petugas,
                                        )}
                                    >
                                        {formatValue(
                                            row.petugas,
                                        )}
                                    </td>


                                    <td>
                                        {formatValue(
                                            row.regu,
                                        )}
                                    </td>


                                    <td>
                                        {formatValue(
                                            row.waktu_periksa,
                                        )}
                                    </td>

                                </tr>
                            ))}

                    </tbody>
                </table>
            </div>


            {/* ==================================================
             * PAGINATION
             * ================================================== */}

            <div className="customer-table-pagination">

                <button
                    type="button"
                    className="pagination-button"
                    disabled={
                        loading ||
                        page <= 1
                    }
                    onClick={() =>
                        goToPage(
                            page - 1,
                        )
                    }
                >
                    Sebelumnya
                </button>


                <div className="pagination-pages">
                    <span>
                        Halaman{" "}
                        {page} dari{" "}
                        {totalPages}
                    </span>
                </div>


                <button
                    type="button"
                    className="pagination-button"
                    disabled={
                        loading ||
                        page >=
                            totalPages
                    }
                    onClick={() =>
                        goToPage(
                            page + 1,
                        )
                    }
                >
                    Berikutnya
                </button>

            </div>

        </div>
    );
}
