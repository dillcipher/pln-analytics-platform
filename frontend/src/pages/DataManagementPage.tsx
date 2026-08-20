import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import api from "../api/api";

/* =========================================================
 * TYPES
 * ========================================================= */

interface DatasetColumn {
    key: string;
    label: string;
    dtype?: string;
}

interface DatasetCatalogItem {
    key: string;
    label: string;
    group: "SUSPECT" | "DLPD" | string;
    description?: string;
    source?: string;
    columns: DatasetColumn[];
    filter_keys: string[];
}

interface FilterOption {
    key: string;
    label: string;
    values: string[];
}

interface PreviewResponse {
    dataset: string;
    columns: DatasetColumn[];
    rows: Record<string, unknown>[];
    total_rows: number;
}

interface OverviewData {
    total_dataset?: number;
    total_rows?: number;
    total_size_mb?: number;
}

interface JobHistory {
    job_id?: string;
    status?: string;
    created_at?: string;
    started_at?: string;
    finished_at?: string;
}

/* =========================================================
 * CONSTANTS
 * ========================================================= */

const FILTER_ORDER = [
    "month",
    "unitupi",
    "unitap",
    "unitup",
    "tariff",
    "segment",
    "suspect_name",
    "location_code",
    "idpel",
];

const EMPTY_OVERVIEW: OverviewData = {
    total_dataset: 0,
    total_rows: 0,
    total_size_mb: 0,
};

const DEFAULT_PREVIEW_LIMIT = 100;

/* =========================================================
 * HELPERS
 * ========================================================= */

function unwrap<T>(value: unknown): T {
    if (
        value &&
        typeof value === "object" &&
        !Array.isArray(value)
    ) {
        const record =
            value as Record<string, unknown>;

        if (record.data !== undefined) {
            return record.data as T;
        }

        if (record.result !== undefined) {
            return record.result as T;
        }
    }

    return value as T;
}

function formatNumber(value: unknown): string {
    const number = Number(value ?? 0);

    if (!Number.isFinite(number)) {
        return "0";
    }

    return number.toLocaleString("id-ID");
}


function safeValue(value: unknown): string {
    if (
        value === undefined ||
        value === null ||
        String(value).trim() === ""
    ) {
        return "-";
    }

    return String(value);
}

function filenameSafe(value: string): string {
    return value
        .trim()
        .replace(/[^a-zA-Z0-9._-]+/g, "_")
        .replace(/^_+|_+$/g, "");
}

/* =========================================================
 * API
 * ========================================================= */

async function getCatalog(): Promise<DatasetCatalogItem[]> {
    const response = await api.get(
        "/data-management/catalog",
    );

    const data =
        unwrap<unknown>(response.data);

    return Array.isArray(data)
        ? data as DatasetCatalogItem[]
        : [];
}

async function getFilters(
    dataset: string,
    month?: string,
): Promise<FilterOption[]> {
    const response = await api.get(
        "/data-management/filters",
        {
            params: {
                dataset,
                ...(month
                    ? { month }
                    : {}),
            },
        },
    );

    const data =
        unwrap<unknown>(response.data);

    return Array.isArray(data)
        ? data as FilterOption[]
        : [];
}

async function getPreview(
    dataset: string,
    filters: Record<string, string>,
    limit = DEFAULT_PREVIEW_LIMIT,
): Promise<PreviewResponse> {
    const params: Record<string, string | number> = {
        dataset,
        limit,
    };

    Object.entries(filters).forEach(
        ([key, value]) => {
            if (value.trim()) {
                params[key] = value;
            }
        },
    );

    const response = await api.get(
        "/data-management/preview",
        {
            params,
        },
    );

    return unwrap<PreviewResponse>(
        response.data,
    );
}

async function getOverview(): Promise<OverviewData> {
    const response = await api.get(
        "/data-management/overview",
    );

    return (
        unwrap<OverviewData>(
            response.data,
        ) ?? EMPTY_OVERVIEW
    );
}

async function getHistory(): Promise<JobHistory[]> {
    const response = await api.get(
        "/history",
    );

    const data =
        unwrap<unknown>(response.data);

    return Array.isArray(data)
        ? data as JobHistory[]
        : [];
}

/* =========================================================
 * COMPONENT
 * ========================================================= */

export default function DataManagementPage() {
    /* -----------------------------------------------------
     * CATALOG
     * ----------------------------------------------------- */

    const [catalog, setCatalog] =
        useState<DatasetCatalogItem[]>([]);

    const [selectedGroup, setSelectedGroup] =
        useState<"SUSPECT" | "DLPD">(
            "SUSPECT",
        );

    const [selectedDataset, setSelectedDataset] =
        useState<string>("");

    /* -----------------------------------------------------
     * FILTERS
     * ----------------------------------------------------- */

    const [filterOptions, setFilterOptions] =
        useState<FilterOption[]>([]);

    const [filters, setFilters] =
        useState<Record<string, string>>({});

    /* -----------------------------------------------------
     * COLUMNS
     * ----------------------------------------------------- */

    const [selectedColumns, setSelectedColumns] =
        useState<string[]>([]);

    /* -----------------------------------------------------
     * PREVIEW
     * ----------------------------------------------------- */

    const [preview, setPreview] =
        useState<PreviewResponse | null>(
            null,
        );

    const [previewLoading, setPreviewLoading] =
        useState(false);

    /* -----------------------------------------------------
     * GENERAL LOADING
     * ----------------------------------------------------- */

    const [catalogLoading, setCatalogLoading] =
        useState(true);

    const [filtersLoading, setFiltersLoading] =
        useState(false);

    const [downloadLoading, setDownloadLoading] =
        useState(false);

    const [error, setError] =
        useState("");

    const [success, setSuccess] =
        useState("");

    /* -----------------------------------------------------
     * OVERVIEW / HISTORY
     * ----------------------------------------------------- */

    const [overview, setOverview] =
        useState<OverviewData>(
            EMPTY_OVERVIEW,
        );

    const [history, setHistory] =
        useState<JobHistory[]>([]);

    /* =====================================================
     * LOAD CATALOG
     * ===================================================== */

    const loadCatalog =
        useCallback(
            async () => {
                setCatalogLoading(true);
                setError("");

                try {
                    const [
                        catalogResult,
                        overviewResult,
                        historyResult,
                    ] =
                        await Promise.all([
                            getCatalog(),
                            getOverview(),
                            getHistory(),
                        ]);

                    setCatalog(
                        catalogResult,
                    );

                    setOverview(
                        overviewResult ??
                        EMPTY_OVERVIEW,
                    );

                    setHistory(
                        historyResult,
                    );

                    /*
                     * Default ke dataset pertama
                     * dari group SUSPECT.
                     */
                    const firstSuspect =
                        catalogResult.find(
                            (item) =>
                                item.group ===
                                "SUSPECT",
                        );

                    if (
                        firstSuspect
                    ) {
                        setSelectedDataset(
                            firstSuspect.key,
                        );
                    }
                } catch (err) {
                    console.error(
                        "Data Management catalog error:",
                        err,
                    );

                    setError(
                        "Gagal memuat catalog Data Management. Pastikan backend aktif dan endpoint tersedia.",
                    );
                } finally {
                    setCatalogLoading(
                        false,
                    );
                }
            },
            [],
        );

    useEffect(() => {
        void loadCatalog();
    }, [loadCatalog]);

    /* =====================================================
     * GROUPED DATASETS
     * ===================================================== */

    const suspectDatasets =
        useMemo(
            () =>
                catalog.filter(
                    (item) =>
                        item.group ===
                        "SUSPECT",
                ),
            [catalog],
        );

    const dlpdDatasets =
        useMemo(
            () =>
                catalog.filter(
                    (item) =>
                        item.group ===
                        "DLPD",
                ),
            [catalog],
        );

    const currentDatasets =
        selectedGroup === "SUSPECT"
            ? suspectDatasets
            : dlpdDatasets;

    const currentDataset =
        catalog.find(
            (item) =>
                item.key ===
                selectedDataset,
        ) ?? null;

    /* =====================================================
     * ENSURE DATASET MATCHES GROUP
     * ===================================================== */

    useEffect(() => {
        if (
            currentDatasets.length === 0
        ) {
            setSelectedDataset("");
            return;
        }

        const exists =
            currentDatasets.some(
                (item) =>
                    item.key ===
                    selectedDataset,
            );

        if (!exists) {
            setSelectedDataset(
                currentDatasets[0].key,
            );
        }
    }, [
        currentDatasets,
        selectedDataset,
    ]);

    /* =====================================================
     * LOAD FILTER OPTIONS
     * ===================================================== */

    const loadFilterOptions =
        useCallback(
            async (
                datasetKey: string,
                month?: string,
            ) => {
                if (!datasetKey) {
                    setFilterOptions([]);
                    return;
                }

                setFiltersLoading(true);
                setError("");

                try {
                    const result =
                        await getFilters(
                            datasetKey,
                            month,
                        );

                    setFilterOptions(
                        result,
                    );
                } catch (err) {
                    console.error(
                        "Filter loading error:",
                        err,
                    );

                    setFilterOptions([]);

                    setError(
                        "Gagal memuat pilihan filter dataset.",
                    );
                } finally {
                    setFiltersLoading(
                        false,
                    );
                }
            },
            [],
        );

    /* =====================================================
     * DATASET CHANGE
     * ===================================================== */

    useEffect(() => {
        if (!selectedDataset) {
            return;
        }

        const dataset =
            catalog.find(
                (item) =>
                    item.key ===
                    selectedDataset,
            );

        if (!dataset) {
            return;
        }

        /*
         * Default semua kolom terpilih.
         */
        setSelectedColumns(
            dataset.columns.map(
                (column) =>
                    column.key,
            ),
        );

        /*
         * Reset filters.
         */
        setFilters({});

        /*
         * Reset preview.
         */
        setPreview(null);

        /*
         * Load filter values.
         */
        void loadFilterOptions(
            selectedDataset,
        );
    }, [
        selectedDataset,
        catalog,
        loadFilterOptions,
    ]);

    /* =====================================================
     * FILTER CHANGE
     * ===================================================== */

    const updateFilter = (
        key: string,
        value: string,
    ) => {
        setFilters(
            (previous) => ({
                ...previous,
                [key]: value,
            }),
        );

        setSuccess("");
    };

    /* =====================================================
     * MONTH CHANGE
     *
     * Reload filter options supaya
     * pilihan Unit / Tarif / Segment
     * mengikuti bulan yang dipilih.
     * ===================================================== */

    const handleMonthChange = async (
        value: string,
    ) => {
        updateFilter(
            "month",
            value,
        );

        await loadFilterOptions(
            selectedDataset,
            value || undefined,
        );
    };

    /* =====================================================
     * RESET FILTER
     * ===================================================== */

    const resetFilters = async () => {
        setFilters({});
        setPreview(null);
        setSuccess("");

        await loadFilterOptions(
            selectedDataset,
        );
    };

    /* =====================================================
     * COLUMN ACTIONS
     * ===================================================== */

    const selectAllColumns = () => {
        if (!currentDataset) {
            return;
        }

        setSelectedColumns(
            currentDataset.columns.map(
                (column) =>
                    column.key,
            ),
        );
    };

    const clearAllColumns = () => {
        setSelectedColumns([]);
    };

    const toggleColumn = (
        columnKey: string,
    ) => {
        setSelectedColumns(
            (previous) => {
                if (
                    previous.includes(
                        columnKey,
                    )
                ) {
                    return previous.filter(
                        (item) =>
                            item !==
                            columnKey,
                    );
                }

                return [
                    ...previous,
                    columnKey,
                ];
            },
        );
    };

    /* =====================================================
     * APPLY / PREVIEW
     * ===================================================== */

    const applyPreview = async () => {
        if (!selectedDataset) {
            setError(
                "Pilih dataset terlebih dahulu.",
            );
            return;
        }

        setPreviewLoading(true);
        setError("");
        setSuccess("");

        try {
            const result =
                await getPreview(
                    selectedDataset,
                    filters,
                );

            setPreview(
                result,
            );

            setSuccess(
                `Preview berhasil dimuat: ${formatNumber(
                    result.total_rows,
                )} record ditemukan.`,
            );
        } catch (err) {
            console.error(
                "Preview error:",
                err,
            );

            setPreview(null);

            setError(
                "Gagal memuat preview data.",
            );
        } finally {
            setPreviewLoading(
                false,
            );
        }
    };

    /* =====================================================
     * DOWNLOAD
     * ===================================================== */

    const downloadData =
        async () => {
            if (
                !selectedDataset
            ) {
                setError(
                    "Pilih dataset terlebih dahulu.",
                );
                return;
            }

            if (
                selectedColumns.length ===
                0
            ) {
                setError(
                    "Pilih minimal satu kolom untuk di-download.",
                );
                return;
            }

            setDownloadLoading(
                true,
            );

            setError("");
            setSuccess("");

            try {
                const params: Record<
                    string,
                    string
                > = {
                    dataset:
                        selectedDataset,
                    columns:
                        selectedColumns.join(
                            ",",
                        ),
                };

                Object.entries(
                    filters,
                ).forEach(
                    ([
                        key,
                        value,
                    ]) => {
                        if (
                            value.trim()
                        ) {
                            params[key] =
                                value;
                        }
                    },
                );

                const response =
                    await api.get(
                        "/data-management/export",
                        {
                            params,
                            responseType:
                                "blob",
                        },
                    );

                const blob =
                    response.data as Blob;

                const url =
                    window.URL.createObjectURL(
                        blob,
                    );

                const anchor =
                    document.createElement(
                        "a",
                    );

                anchor.href = url;

                const month =
                    filters.month
                        ? `_${filenameSafe(
                              filters.month,
                          )}`
                        : "";

                anchor.download =
                    `${filenameSafe(
                        selectedDataset,
                    )}${month}.csv`;

                document.body.appendChild(
                    anchor,
                );

                anchor.click();

                anchor.remove();

                window.URL.revokeObjectURL(
                    url,
                );

                setSuccess(
                    `Download ${selectedDataset} berhasil dimulai.`,
                );
            } catch (err) {
                console.error(
                    "Export error:",
                    err,
                );

                setError(
                    "Gagal melakukan download. Periksa filter, kolom, dan status backend.",
                );
            } finally {
                setDownloadLoading(
                    false,
                );
            }
        };

    /* =====================================================
     * FILTER MAP
     * ===================================================== */

    const orderedFilters =
        useMemo(() => {
            return [
                ...FILTER_ORDER.filter(
                    (key) =>
                        filterOptions.some(
                            (item) =>
                                item.key ===
                                key,
                        ),
                ),
                ...filterOptions
                    .map(
                        (item) =>
                            item.key,
                    )
                    .filter(
                        (key) =>
                            !FILTER_ORDER.includes(
                                key,
                            ),
                    ),
            ];
        }, [filterOptions]);

    /* =====================================================
     * PREVIEW COLUMNS
     *
     * Preview tetap menampilkan seluruh
     * column yang dikirim backend,
     * tetapi user bisa memilih subset
     * yang mau dilihat.
     * ===================================================== */

    const visiblePreviewColumns =
        useMemo(() => {
            if (!preview) {
                return [];
            }

            if (
                selectedColumns.length ===
                0
            ) {
                return preview.columns;
            }

            return preview.columns.filter(
                (column) =>
                    selectedColumns.includes(
                        column.key,
                    ),
            );
        }, [
            preview,
            selectedColumns,
        ]);

    /* =====================================================
     * RENDER
     * ===================================================== */

    return (
        <div className="export-page">

            {/* =================================================
             * HERO
             * ================================================= */}

            <div className="export-hero">

                <div>
                    <h1>
                        Data Management
                    </h1>

                    <p>
                        Pusat pengambilan data
                        PLN Analytics. Pilih
                        kelompok data, dataset,
                        filter, dan kolom yang
                        dibutuhkan sebelum
                        melakukan download.
                    </p>
                </div>

                <div
                    style={{
                        display:
                            "flex",
                        gap: 8,
                        flexWrap:
                            "wrap",
                    }}
                >
                    <span className="export-badge">
                        {formatNumber(
                            overview.total_dataset,
                        )}{" "}
                        Dataset
                    </span>

                    <span className="export-badge">
                        {formatNumber(
                            overview.total_rows,
                        )}{" "}
                        Records
                    </span>
                </div>
            </div>

            {/* =================================================
             * ERROR
             * ================================================= */}

            {error && (
                <div
                    className="system-error"
                    role="alert"
                    style={{
                        marginBottom:
                            18,
                    }}
                >
                    <strong>
                        Error
                    </strong>

                    <span>
                        {error}
                    </span>
                </div>
            )}

            {/* =================================================
             * SUCCESS
             * ================================================= */}

            {success && (
                <div
                    style={{
                        marginBottom:
                            18,
                        padding:
                            "12px 15px",
                        border:
                            "1px solid rgba(24, 210, 110, 0.3)",
                        borderRadius:
                            9,
                        background:
                            "rgba(24, 210, 110, 0.08)",
                        color:
                            "#54df91",
                        fontSize:
                            12,
                    }}
                >
                    {success}
                </div>
            )}

            {/* =================================================
             * MAIN
             * ================================================= */}

            <div className="export-content">

                {/* =============================================
                 * LEFT
                 * ============================================= */}

                <div>

                    <section className="export-panel">

                        {/* -------------------------------------
                         * GROUP
                         * ------------------------------------- */}

                        <div className="export-panel-header">

                            <h2>
                                Pilih Kelompok Data
                            </h2>

                            <p>
                                Tentukan apakah
                                data yang ingin
                                diambil berasal
                                dari Suspect atau
                                DLPD.
                            </p>

                        </div>

                        <div className="export-source-grid">

                            <button
                                type="button"
                                className={
                                    selectedGroup ===
                                    "SUSPECT"
                                        ? "export-source-card active"
                                        : "export-source-card"
                                }
                                onClick={() => {
                                    setSelectedGroup(
                                        "SUSPECT",
                                    );
                                    setSuccess(
                                        "",
                                    );
                                    setError(
                                        "",
                                    );
                                }}
                            >
                                <strong>
                                    SUSPECT
                                </strong>

                                <span>
                                    ANEV,
                                    repeat
                                    location,
                                    dan
                                    pemeriksaan
                                    suspect.
                                </span>
                            </button>

                            <button
                                type="button"
                                className={
                                    selectedGroup ===
                                    "DLPD"
                                        ? "export-source-card active"
                                        : "export-source-card"
                                }
                                onClick={() => {
                                    setSelectedGroup(
                                        "DLPD",
                                    );
                                    setSuccess(
                                        "",
                                    );
                                    setError(
                                        "",
                                    );
                                }}
                            >
                                <strong>
                                    DLPD
                                </strong>

                                <span>
                                    Prabayar,
                                    Pascabayar,
                                    gabungan,
                                    dan
                                    pemeriksaan.
                                </span>
                            </button>

                        </div>

                        {/* -------------------------------------
                         * DATASET
                         * ------------------------------------- */}

                        <div className="export-section">

                            <div className="export-section-title">

                                <h3>
                                    Dataset
                                </h3>

                                <span>
                                    {
                                        currentDatasets.length
                                    }{" "}
                                    pilihan
                                </span>

                            </div>

                            {catalogLoading ? (
                                <div
                                    className="export-empty"
                                    style={{
                                        minHeight:
                                            100,
                                    }}
                                >
                                    Memuat
                                    catalog
                                    dataset...
                                </div>
                            ) : (
                                <div className="export-source-grid">
                                    {currentDatasets.map(
                                        (
                                            dataset,
                                        ) => (
                                            <button
                                                type="button"
                                                key={
                                                    dataset.key
                                                }
                                                className={
                                                    selectedDataset ===
                                                    dataset.key
                                                        ? "export-source-card active"
                                                        : "export-source-card"
                                                }
                                                onClick={() =>
                                                    setSelectedDataset(
                                                        dataset.key,
                                                    )
                                                }
                                            >
                                                <strong>
                                                    {
                                                        dataset.label
                                                    }
                                                </strong>

                                                <span>
                                                    {
                                                        dataset.description ??
                                                        dataset.source ??
                                                        "Dataset"
                                                    }
                                                </span>

                                                <span
                                                    style={{
                                                        marginTop:
                                                            8,
                                                        color:
                                                            "#5f8ecb",
                                                    }}
                                                >
                                                    {
                                                        dataset.columns
                                                            .length
                                                    }{" "}
                                                    kolom
                                                </span>
                                            </button>
                                        ),
                                    )}
                                </div>
                            )}

                        </div>

                        {/* -------------------------------------
                         * FILTERS
                         * ------------------------------------- */}

                        <div className="export-section">

                            <div className="export-section-title">

                                <h3>
                                    Filter Data
                                </h3>

                                <span>
                                    {filtersLoading
                                        ? "Memuat..."
                                        : `${orderedFilters.length} filter tersedia`}
                                </span>

                            </div>

                            {orderedFilters.length ===
                            0 ? (
                                <div
                                    className="export-empty"
                                    style={{
                                        minHeight:
                                            100,
                                    }}
                                >
                                    Tidak ada
                                    filter
                                    khusus
                                    untuk
                                    dataset
                                    ini.
                                </div>
                            ) : (
                                <div className="export-form">

                                    <div className="export-form-grid">

                                        {orderedFilters.map(
                                            (
                                                filterKey,
                                            ) => {
                                                const option =
                                                    filterOptions.find(
                                                        (
                                                            item,
                                                        ) =>
                                                            item.key ===
                                                            filterKey,
                                                    );

                                                if (
                                                    !option
                                                ) {
                                                    return null;
                                                }

                                                const currentValue =
                                                    filters[
                                                        filterKey
                                                    ] ??
                                                    "";

                                                return (
                                                    <div
                                                        className="export-field"
                                                        key={
                                                            filterKey
                                                        }
                                                    >
                                                        <label>
                                                            {
                                                                option.label
                                                            }
                                                        </label>

                                                        <select
                                                            value={
                                                                currentValue
                                                            }
                                                            onChange={(
                                                                event,
                                                            ) => {
                                                                if (
                                                                    filterKey ===
                                                                    "month"
                                                                ) {
                                                                    void handleMonthChange(
                                                                        event
                                                                            .target
                                                                            .value,
                                                                    );
                                                                } else {
                                                                    updateFilter(
                                                                        filterKey,
                                                                        event
                                                                            .target
                                                                            .value,
                                                                    );
                                                                }
                                                            }}
                                                        >
                                                            <option value="">
                                                                Semua
                                                            </option>

                                                            {option.values.map(
                                                                (
                                                                    value,
                                                                ) => (
                                                                    <option
                                                                        key={`${filterKey}-${value}`}
                                                                        value={
                                                                            value
                                                                        }
                                                                    >
                                                                        {
                                                                            value
                                                                        }
                                                                    </option>
                                                                ),
                                                            )}
                                                        </select>
                                                    </div>
                                                );
                                            },
                                        )}

                                    </div>

                                </div>
                            )}

                            <div className="export-actions">

                                <button
                                    type="button"
                                    className="export-button secondary"
                                    onClick={() =>
                                        void resetFilters()
                                    }
                                >
                                    Reset Filter
                                </button>

                                <button
                                    type="button"
                                    className="export-button"
                                    disabled={
                                        previewLoading ||
                                        !selectedDataset
                                    }
                                    onClick={() =>
                                        void applyPreview()
                                    }
                                >
                                    {previewLoading
                                        ? "Memuat Preview..."
                                        : "Terapkan & Preview"}
                                </button>

                            </div>

                        </div>

                        {/* -------------------------------------
                         * COLUMNS
                         * ------------------------------------- */}

                        <div className="export-section">

                            <div className="export-section-title">

                                <h3>
                                    Kolom yang
                                    Di-download
                                </h3>

                                <span>
                                    {
                                        selectedColumns.length
                                    }{" "}
                                    /{" "}
                                    {
                                        currentDataset?.columns
                                            .length ??
                                        0
                                    }
                                </span>

                            </div>

                            <div className="column-actions">

                                <button
                                    type="button"
                                    onClick={
                                        selectAllColumns
                                    }
                                >
                                    Pilih Semua
                                </button>

                                <button
                                    type="button"
                                    onClick={
                                        clearAllColumns
                                    }
                                >
                                    Kosongkan
                                </button>

                            </div>

                            <div className="column-selector">

                                {currentDataset?.columns.map(
                                    (
                                        column,
                                    ) => {
                                        const checked =
                                            selectedColumns.includes(
                                                column.key,
                                            );

                                        return (
                                            <label
                                                key={
                                                    column.key
                                                }
                                                className={
                                                    checked
                                                        ? "column-option selected"
                                                        : "column-option"
                                                }
                                                title={
                                                    column.dtype ??
                                                    ""
                                                }
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={
                                                        checked
                                                    }
                                                    onChange={() =>
                                                        toggleColumn(
                                                            column.key,
                                                        )
                                                    }
                                                />

                                                <span>
                                                    {
                                                        column.label
                                                    }
                                                </span>
                                            </label>
                                        );
                                    },
                                )}

                            </div>

                        </div>

                        {/* -------------------------------------
                         * EXPORT
                         * ------------------------------------- */}

                        <div className="export-actions">

                            <button
                                type="button"
                                className="export-button secondary"
                                onClick={() =>
                                    void applyPreview()
                                }
                                disabled={
                                    previewLoading ||
                                    !selectedDataset
                                }
                            >
                                Preview
                            </button>

                            <button
                                type="button"
                                className="export-button"
                                onClick={() =>
                                    void downloadData()
                                }
                                disabled={
                                    downloadLoading ||
                                    !selectedDataset ||
                                    selectedColumns.length ===
                                        0
                                }
                            >
                                {downloadLoading
                                    ? "Menyiapkan Download..."
                                    : "Download CSV"}
                            </button>

                        </div>

                    </section>

                    {/* =========================================
                     * PREVIEW
                     * ========================================= */}

                    <section className="export-preview">

                        <div className="export-preview-header">

                            <div>
                                <h2>
                                    Preview Data
                                </h2>

                                <p>
                                    Menampilkan
                                    sebagian
                                    data hasil
                                    filter
                                    sebelum
                                    download.
                                </p>
                            </div>

                            <span className="export-preview-count">
                                {preview
                                    ? `${formatNumber(
                                          preview.total_rows,
                                      )} record`
                                    : "Belum ada preview"}
                            </span>

                        </div>

                        {!preview ? (
                            <div className="export-empty">
                                Pilih dataset,
                                tentukan filter,
                                lalu klik
                                <strong
                                    style={{
                                        marginLeft:
                                            4,
                                    }}
                                >
                                    Terapkan &
                                    Preview
                                </strong>
                                .
                            </div>
                        ) : preview.rows.length ===
                          0 ? (
                            <div className="export-empty">
                                Tidak ada data
                                yang cocok
                                dengan filter
                                yang dipilih.
                            </div>
                        ) : (
                            <div className="export-preview-table-wrap">

                                <table className="export-preview-table">

                                    <thead>
                                        <tr>
                                            {visiblePreviewColumns.map(
                                                (
                                                    column,
                                                ) => (
                                                    <th
                                                        key={
                                                            column.key
                                                        }
                                                    >
                                                        {
                                                            column.label
                                                        }
                                                    </th>
                                                ),
                                            )}
                                        </tr>
                                    </thead>

                                    <tbody>
                                        {preview.rows.map(
                                            (
                                                row,
                                                index,
                                            ) => (
                                                <tr
                                                    key={`preview-${index}`}
                                                >
                                                    {visiblePreviewColumns.map(
                                                        (
                                                            column,
                                                        ) => (
                                                            <td
                                                                key={
                                                                    column.key
                                                                }
                                                            >
                                                                {safeValue(
                                                                    row[
                                                                        column.key
                                                                    ],
                                                                )}
                                                            </td>
                                                        ),
                                                    )}
                                                </tr>
                                            ),
                                        )}
                                    </tbody>

                                </table>

                            </div>
                        )}

                    </section>

                </div>

                {/* =============================================
                 * RIGHT SUMMARY
                 * ============================================= */}

                <aside className="export-summary">

                    <div className="export-summary-header">

                        <h2>
                            Export Summary
                        </h2>

                        <p>
                            Ringkasan data
                            yang akan
                            diambil.
                        </p>

                    </div>

                    <div className="export-summary-body">

                        <div className="export-summary-stat">
                            <span>
                                Kelompok
                            </span>

                            <strong>
                                {selectedGroup}
                            </strong>
                        </div>

                        <div className="export-summary-stat">
                            <span>
                                Dataset
                            </span>

                            <strong>
                                {currentDataset
                                    ? currentDataset.label
                                    : "-"}
                            </strong>
                        </div>

                        <div className="export-summary-stat">
                            <span>
                                Kolom
                            </span>

                            <strong>
                                {
                                    selectedColumns.length
                                }
                            </strong>
                        </div>

                        <div className="export-summary-stat">
                            <span>
                                Filter Aktif
                            </span>

                            <strong>
                                {
                                    Object.values(
                                        filters,
                                    ).filter(
                                        (
                                            value,
                                        ) =>
                                            value.trim() !==
                                            "",
                                    ).length
                                }
                            </strong>
                        </div>

                        <div className="export-summary-stat">
                            <span>
                                Preview
                            </span>

                            <strong>
                                {preview
                                    ? formatNumber(
                                          preview.total_rows,
                                      )
                                    : "-"}
                            </strong>
                        </div>

                        <div className="export-summary-stat">
                            <span>
                                Format
                            </span>

                            <strong>
                                CSV
                            </strong>
                        </div>

                    </div>

                    {/* -----------------------------------------
                     * ACTIVE FILTERS
                     * ----------------------------------------- */}

                    <div
                        className="export-section"
                        style={{
                            padding:
                                "15px",
                        }}
                    >

                        <div className="export-section-title">
                            <h3>
                                Filter Aktif
                            </h3>
                        </div>

                        {Object.entries(
                            filters,
                        ).filter(
                            ([, value]) =>
                                value.trim() !==
                                "",
                        ).length ===
                        0 ? (
                            <div
                                style={{
                                    color:
                                        "#637b9c",
                                    fontSize:
                                        11,
                                }}
                            >
                                Tidak ada
                                filter.
                                Semua data
                                dataset
                                akan
                                digunakan.
                            </div>
                        ) : (
                            <div
                                style={{
                                    display:
                                        "flex",
                                    flexDirection:
                                        "column",
                                    gap: 7,
                                }}
                            >
                                {Object.entries(
                                    filters,
                                )
                                    .filter(
                                        (
                                            [
                                                ,
                                                value,
                                            ],
                                        ) =>
                                            value.trim() !==
                                            "",
                                    )
                                    .map(
                                        ([
                                            key,
                                            value,
                                        ]) => {
                                            const label =
                                                filterOptions.find(
                                                    (
                                                        item,
                                                    ) =>
                                                        item.key ===
                                                        key,
                                                )?.label ??
                                                key;

                                            return (
                                                <div
                                                    key={
                                                        key
                                                    }
                                                    style={{
                                                        display:
                                                            "flex",
                                                        justifyContent:
                                                            "space-between",
                                                        gap: 10,
                                                        padding:
                                                            "7px 8px",
                                                        border:
                                                            "1px solid #263954",
                                                        borderRadius:
                                                            6,
                                                        background:
                                                            "rgba(8,17,31,.3)",
                                                    }}
                                                >
                                                    <span
                                                        style={{
                                                            color:
                                                                "#7891b2",
                                                            fontSize:
                                                                10,
                                                        }}
                                                    >
                                                        {
                                                            label
                                                        }
                                                    </span>

                                                    <strong
                                                        style={{
                                                            color:
                                                                "#dce7f5",
                                                            fontSize:
                                                                10,
                                                            textAlign:
                                                                "right",
                                                        }}
                                                    >
                                                        {
                                                            value
                                                        }
                                                    </strong>
                                                </div>
                                            );
                                        },
                                    )}
                            </div>
                        )}

                    </div>

                </aside>

            </div>

            {/* =================================================
             * HISTORY
             * ================================================= */}

            <section
                className="export-preview"
                style={{
                    marginTop: 18,
                }}
            >

                <div className="export-preview-header">

                    <div>
                        <h2>
                            ETL / Upload History
                        </h2>

                        <p>
                            Riwayat proses data
                            yang masuk ke
                            warehouse.
                        </p>
                    </div>

                    <span className="export-preview-count">
                        {
                            history.length
                        }{" "}
                        job
                    </span>

                </div>

                {history.length ===
                0 ? (
                    <div className="export-empty">
                        Belum ada riwayat
                        ETL.
                    </div>
                ) : (
                    <div className="system-table-wrap">

                        <table className="system-table">

                            <thead>
                                <tr>
                                    <th>
                                        Job
                                    </th>

                                    <th>
                                        Status
                                    </th>

                                    <th>
                                        Dibuat
                                    </th>

                                    <th>
                                        Selesai
                                    </th>
                                </tr>
                            </thead>

                            <tbody>
                                {history
                                    .slice(
                                        0,
                                        20,
                                    )
                                    .map(
                                        (
                                            job,
                                            index,
                                        ) => (
                                            <tr
                                                key={`${job.job_id ?? "job"}-${index}`}
                                            >
                                                <td>
                                                    <strong>
                                                        {
                                                            job.job_id ??
                                                            "-"
                                                        }
                                                    </strong>
                                                </td>

                                                <td>
                                                    <span className="status-chip">
                                                        {
                                                            job.status ??
                                                            "-"
                                                        }
                                                    </span>
                                                </td>

                                                <td>
                                                    {safeValue(
                                                        job.created_at ??
                                                        job.started_at,
                                                    )}
                                                </td>

                                                <td>
                                                    {safeValue(
                                                        job.finished_at,
                                                    )}
                                                </td>
                                            </tr>
                                        ),
                                    )}
                            </tbody>

                        </table>

                    </div>
                )}

            </section>

        </div>
    );
}