import "./DlpdPage.css";

import {
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    getDlpdDashboard,
    getDlpdFilters,
    getDlpdMapPoints,
    getDlpdMonths,
} from "../api/dlpd";

import type {
    CustomerType,
    DlpdDashboard,
    DlpdFilters,
    DlpdMapPoint,
    MonthOption,
} from "../api/dlpd";

import DlpdUnitTable from "../components/dlpd/DlpdUnitTable";
import DlpdDetail from "../components/dlpd/DlpdDetail";
import DlpdCustomerTable from "../components/dlpd/DlpdCustomerTable";
import DlpdMap from "../components/dlpd/DlpdMap";


/* ==========================================================
 * DEFAULT DATA
 * ========================================================== */

const EMPTY_DASHBOARD: DlpdDashboard = {
    total_target: 0,
    normal: 0,
    temuan: 0,
    belum_periksa: 0,
    sudah_periksa: 0,
    progress_pct: 0,
};


const EMPTY_FILTERS: DlpdFilters = {
    months: [],
    unitupi: [],
    unitap: [],
    unitup: [],
    status: [],
    inspection_status: [],
    dlpd_repeat: [],
    kendala: [],
};


/* ==========================================================
 * SPECIAL MONTH VALUE
 * ========================================================== */

/**
 * Nilai internal untuk mode "Semua Bulan".
 *
 * Jangan gunakan "" karena "" tetap dipakai sebagai
 * placeholder "Pilih Bulan".
 */
const ALL_MONTHS = "__ALL_MONTHS__";


/* ==========================================================
 * HELPERS
 * ========================================================== */

function isValidMonthKey(
    value: unknown,
): value is string {
    return (
        typeof value === "string" &&
        /^\d{6}$/.test(value.trim())
    );
}


/**
 * Convert YYYYMM -> label.
 *
 * Contoh:
 * 202601 -> Januari 2026
 * 202606 -> Juni 2026
 */
function monthKeyToLabel(
    monthKey: string,
): string {
    if (!isValidMonthKey(monthKey)) {
        return monthKey;
    }

    const year = Number(
        monthKey.slice(0, 4),
    );

    const month = Number(
        monthKey.slice(4, 6),
    );

    if (
        month < 1 ||
        month > 12
    ) {
        return monthKey;
    }

    const monthNames = [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ];

    return `${monthNames[month - 1]} ${year}`;
}


/**
 * Normalisasi MonthOption dari backend.
 */
function normalizeMonths(
    result:
        | MonthOption[]
        | undefined
        | null,
): MonthOption[] {
    if (!Array.isArray(result)) {
        return [];
    }

    const unique =
        new Map<
            string,
            MonthOption
        >();

    for (
        const item of result
    ) {
        if (
            !item ||
            !isValidMonthKey(
                item.month_key,
            )
        ) {
            continue;
        }

        const monthKey =
            item.month_key.trim();

        unique.set(
            monthKey,
            {
                month_key: monthKey,
                label:
                    item.label?.trim() ||
                    monthKeyToLabel(
                        monthKey,
                    ),
            },
        );
    }

    return Array.from(
        unique.values(),
    ).sort(
        (a, b) =>
            a.month_key.localeCompare(
                b.month_key,
            ),
    );
}


/**
 * Normalisasi daftar YYYYMM dari endpoint filter.
 */
function normalizeMonthKeys(
    values:
        | string[]
        | undefined
        | null,
): MonthOption[] {
    if (!Array.isArray(values)) {
        return [];
    }

    const unique =
        new Map<
            string,
            MonthOption
        >();

    for (
        const rawValue of values
    ) {
        if (
            typeof rawValue !==
            "string"
        ) {
            continue;
        }

        const monthKey =
            rawValue.trim();

        if (
            !isValidMonthKey(
                monthKey,
            )
        ) {
            continue;
        }

        unique.set(
            monthKey,
            {
                month_key: monthKey,
                label:
                    monthKeyToLabel(
                        monthKey,
                    ),
            },
        );
    }

    return Array.from(
        unique.values(),
    ).sort(
        (a, b) =>
            a.month_key.localeCompare(
                b.month_key,
            ),
    );
}


function mergeMonths(
    ...sources: MonthOption[][]
): MonthOption[] {
    const unique =
        new Map<
            string,
            MonthOption
        >();

    for (
        const source of sources
    ) {
        for (
            const item of source
        ) {
            if (
                !item ||
                !isValidMonthKey(
                    item.month_key,
                )
            ) {
                continue;
            }

            const monthKey =
                item.month_key.trim();

            unique.set(
                monthKey,
                {
                    month_key:
                        monthKey,
                    label:
                        item.label?.trim() ||
                        monthKeyToLabel(
                            monthKey,
                        ),
                },
            );
        }
    }

    return Array.from(
        unique.values(),
    ).sort(
        (a, b) =>
            a.month_key.localeCompare(
                b.month_key,
            ),
    );
}


function normalizeOptions(
    values:
        | string[]
        | undefined
        | null,
): string[] {
    if (!Array.isArray(values)) {
        return [];
    }

    return Array.from(
        new Set(
            values
                .filter(
                    (
                        value,
                    ) =>
                        typeof value ===
                            "string" &&
                        value.trim() !== "",
                )
                .map(
                    (
                        value,
                    ) =>
                        value.trim(),
                ),
        ),
    );
}


/* ==========================================================
 * MAP DATA
 * ========================================================== */

interface DlpdMapStats {
    total: number;
    location_matched: number;
    mapped: number;
    unmapped: number;
}


const EMPTY_MAP_STATS: DlpdMapStats = {
    total: 0,
    location_matched: 0,
    mapped: 0,
    unmapped: 0,
};


/* ==========================================================
 * PAGE
 * ========================================================== */

export default function DlpdPage() {

    /* ======================================================
     * CUSTOMER TYPE
     * ====================================================== */

    const [
        customerType,
        setCustomerType,
    ] = useState<CustomerType>(
        "prabayar",
    );


    /* ======================================================
     * MONTH CACHE
     * ====================================================== */

    const [
        monthCache,
        setMonthCache,
    ] = useState<
        Record<
            CustomerType,
            MonthOption[]
        >
    >({
        prabayar: [],
        pascabayar: [],
    });


    /**
     * month:
     *
     * undefined
     *   = belum ada bulan dipilih
     *
     * "__ALL_MONTHS__"
     *   = semua bulan
     *
     * "YYYYMM"
     *   = bulan tertentu
     */
    const [
        month,
        setMonth,
    ] = useState<
        string | undefined
    >(undefined);


    const [
        monthLoading,
        setMonthLoading,
    ] = useState(true);


    /* ======================================================
     * FILTER OPTIONS
     * ====================================================== */

    const [
        filters,
        setFilters,
    ] = useState<DlpdFilters>(
        EMPTY_FILTERS,
    );


    /* ======================================================
     * SELECTED FILTERS
     * ====================================================== */

    const [
        selectedUnit,
        setSelectedUnit,
    ] = useState<
        string | undefined
    >(undefined);


    const [
        selectedStatus,
        setSelectedStatus,
    ] = useState<
        string | undefined
    >(undefined);


    const [
        selectedInspectionStatus,
        setSelectedInspectionStatus,
    ] = useState<
        string | undefined
    >(undefined);


    const [
        selectedRepeat,
        setSelectedRepeat,
    ] = useState<
        string | undefined
    >(undefined);


    const [
        selectedKendala,
        setSelectedKendala,
    ] = useState<
        string | undefined
    >(undefined);


    /* ======================================================
     * CUSTOMER DETAIL
     * ====================================================== */

    const [
        selectedIdpel,
        setSelectedIdpel,
    ] = useState<
        string | undefined
    >(undefined);


    /* ======================================================
     * DASHBOARD
     * ====================================================== */

    const [
        dashboard,
        setDashboard,
    ] = useState<DlpdDashboard>(
        EMPTY_DASHBOARD,
    );


    const [
        loading,
        setLoading,
    ] = useState(true);


    const [
        filterLoading,
        setFilterLoading,
    ] = useState(false);


    const [
        pageError,
        setPageError,
    ] = useState<string | null>(
        null,
    );


    /* ======================================================
     * MAP
     * ====================================================== */

    const [
        mapPoints,
        setMapPoints,
    ] = useState<DlpdMapPoint[]>(
        [],
    );


    const [
        mapStats,
        setMapStats,
    ] = useState<DlpdMapStats>(
        EMPTY_MAP_STATS,
    );


    const [
        mapLoading,
        setMapLoading,
    ] = useState(false);


    const [
        mapError,
        setMapError,
    ] = useState<
        string | undefined
    >(undefined);


    /* ======================================================
     * CURRENT MONTHS
     * ====================================================== */

    const currentMonths =
        useMemo(
            () =>
                normalizeMonths(
                    monthCache[
                        customerType
                    ] ?? [],
                ),
            [
                monthCache,
                customerType,
            ],
        );


    /* ======================================================
     * CURRENT KENDALA
     * ====================================================== */

    const currentKendalaOptions =
        useMemo(
            () => {
                return normalizeOptions(
                    filters.kendala,
                ).map(
                    (
                        value,
                    ) => ({
                        value,
                        label: value,
                    }),
                );
            },
            [
                filters.kendala,
            ],
        );


    /* ======================================================
     * MONTH MODE
     * ====================================================== */

    const isAllMonths =
        month === ALL_MONTHS;


    /**
     * Hanya YYYYMM yang dikirim sebagai periode.
     *
     * Untuk Semua Bulan:
     * validMonth = undefined
     *
     * Artinya repository/backend harus tidak menambahkan
     * WHERE MONTH_KEY = ... ketika month undefined.
     */
    const validMonth =
        isValidMonthKey(month)
            ? month
            : undefined;


    /* ======================================================
     * LOAD MONTHS
     *
     * Ambil seluruh periode dari API.
     * ====================================================== */

    useEffect(() => {

        let cancelled = false;

        const loadMonths =
            async () => {

                try {

                    setMonthLoading(
                        true,
                    );

                    setPageError(
                        null,
                    );

                    const result =
                        await getDlpdMonths(
                            customerType,
                        );

                    if (
                        cancelled
                    ) {
                        return;
                    }

                    const normalized =
                        normalizeMonths(
                            result,
                        );

                    setMonthCache(
                        (
                            previous,
                        ) => ({
                            ...previous,
                            [customerType]:
                                normalized,
                        }),
                    );

                    /**
                     * Jika sedang pindah customer type,
                     * pilih bulan terbaru.
                     *
                     * Tetapi jika mode Semua Bulan sudah aktif,
                     * jangan dipaksa kembali ke bulan tertentu.
                     */
                    setMonth(
                        (
                            previousMonth,
                        ) => {

                            if (
                                previousMonth ===
                                ALL_MONTHS
                            ) {
                                return ALL_MONTHS;
                            }

                            const stillExists =
                                normalized.some(
                                    (
                                        item,
                                    ) =>
                                        item.month_key ===
                                        previousMonth,
                                );

                            if (
                                stillExists
                            ) {
                                return previousMonth;
                            }

                            if (
                                normalized.length >
                                0
                            ) {
                                return normalized[
                                    normalized.length -
                                        1
                                ].month_key;
                            }

                            return undefined;
                        },
                    );

                } catch (err) {

                    console.error(
                        "Failed to load DLPD months:",
                        err,
                    );

                    if (
                        !cancelled
                    ) {

                        setPageError(
                            "Gagal memuat periode DLPD. Pastikan backend aktif dan dataset DLPD sudah diproses.",
                        );

                        setMonth(
                            undefined,
                        );
                    }

                } finally {

                    if (
                        !cancelled
                    ) {
                        setMonthLoading(
                            false,
                        );
                    }
                }
            };

        loadMonths();

        return () => {
            cancelled = true;
        };

    }, [
        customerType,
    ]);


    /* ======================================================
     * LOAD FILTER OPTIONS
     *
     * Untuk Semua Bulan:
     * panggil endpoint tanpa month.
     *
     * Backend harus menganggap month undefined sebagai
     * seluruh periode.
     * ====================================================== */

    useEffect(() => {

        if (
            !validMonth &&
            !isAllMonths
        ) {

            setFilters(
                EMPTY_FILTERS,
            );

            setFilterLoading(
                false,
            );

            return;
        }


        let cancelled = false;


        const loadFilters =
            async () => {

                try {

                    setFilterLoading(
                        true,
                    );

                    /**
                     * validMonth:
                     *
                     * YYYYMM -> bulan tertentu
                     * undefined -> Semua Bulan
                     */
                    const result =
                        await getDlpdFilters(
                            customerType,
                            validMonth,
                        );

                    if (
                        cancelled
                    ) {
                        return;
                    }


                    const filterMonths =
                        normalizeMonthKeys(
                            result?.months,
                        );


                    /**
                     * Gabungkan daftar bulan yang diperoleh
                     * dari endpoint months dan filters.
                     */
                    setMonthCache(
                        (
                            previous,
                        ) => {

                            const existing =
                                previous[
                                    customerType
                                ] ?? [];

                            const merged =
                                mergeMonths(
                                    existing,
                                    filterMonths,
                                );

                            return {
                                ...previous,
                                [customerType]:
                                    merged,
                            };
                        },
                    );


                    setFilters({

                        months:
                            filterMonths.length >
                            0
                                ? filterMonths.map(
                                      (
                                          item,
                                      ) =>
                                          item.month_key,
                                  )
                                : normalizeOptions(
                                      result?.months,
                                  ),

                        unitupi:
                            normalizeOptions(
                                result?.unitupi,
                            ),

                        unitap:
                            normalizeOptions(
                                result?.unitap,
                            ),

                        unitup:
                            normalizeOptions(
                                result?.unitup,
                            ),

                        status:
                            normalizeOptions(
                                result?.status,
                            ),

                        inspection_status:
                            normalizeOptions(
                                result?.inspection_status,
                            ),

                        dlpd_repeat:
                            normalizeOptions(
                                result?.dlpd_repeat,
                            ),

                        kendala:
                            normalizeOptions(
                                result?.kendala,
                            ),
                    });

                } catch (err) {

                    console.error(
                        "Failed to load DLPD filters:",
                        err,
                    );

                    if (
                        !cancelled
                    ) {

                        setFilters(
                            EMPTY_FILTERS,
                        );
                    }

                } finally {

                    if (
                        !cancelled
                    ) {

                        setFilterLoading(
                            false,
                        );
                    }
                }
            };


        loadFilters();


        return () => {
            cancelled = true;
        };

    }, [
        customerType,
        validMonth,
        isAllMonths,
    ]);


    /* ======================================================
     * RESET INVALID UNIT
     * ====================================================== */

    useEffect(() => {

        if (
            !selectedUnit ||
            filterLoading ||
            (
                !validMonth &&
                !isAllMonths
            )
        ) {
            return;
        }

        if (
            filters.unitup.length > 0 &&
            !filters.unitup.includes(
                selectedUnit,
            )
        ) {
            setSelectedUnit(
                undefined,
            );
        }

    }, [
        filterLoading,
        filters.unitup,
        selectedUnit,
        validMonth,
        isAllMonths,
    ]);


    /* ======================================================
     * RESET INVALID STATUS
     * ====================================================== */

    useEffect(() => {

        if (
            !selectedStatus ||
            filterLoading ||
            (
                !validMonth &&
                !isAllMonths
            )
        ) {
            return;
        }

        if (
            filters.status.length > 0 &&
            !filters.status.includes(
                selectedStatus,
            )
        ) {
            setSelectedStatus(
                undefined,
            );
        }

    }, [
        filterLoading,
        filters.status,
        selectedStatus,
        validMonth,
        isAllMonths,
    ]);


    /* ======================================================
     * RESET INVALID INSPECTION STATUS
     * ====================================================== */

    useEffect(() => {

        if (
            !selectedInspectionStatus ||
            filterLoading ||
            (
                !validMonth &&
                !isAllMonths
            )
        ) {
            return;
        }

        if (
            filters.inspection_status.length >
                0 &&
            !filters.inspection_status.includes(
                selectedInspectionStatus,
            )
        ) {
            setSelectedInspectionStatus(
                undefined,
            );
        }

    }, [
        filterLoading,
        filters.inspection_status,
        selectedInspectionStatus,
        validMonth,
        isAllMonths,
    ]);


    /* ======================================================
     * RESET INVALID REPEAT
     * ====================================================== */

    useEffect(() => {

        if (
            !selectedRepeat ||
            filterLoading ||
            (
                !validMonth &&
                !isAllMonths
            )
        ) {
            return;
        }

        if (
            customerType !==
            "pascabayar"
        ) {
            setSelectedRepeat(
                undefined,
            );

            return;
        }

        if (
            filters.dlpd_repeat.length >
                0 &&
            !filters.dlpd_repeat.includes(
                selectedRepeat,
            )
        ) {
            setSelectedRepeat(
                undefined,
            );
        }

    }, [
        customerType,
        filterLoading,
        filters.dlpd_repeat,
        selectedRepeat,
        validMonth,
        isAllMonths,
    ]);


    /* ======================================================
     * RESET INVALID KENDALA
     * ====================================================== */

    useEffect(() => {

        if (
            !selectedKendala ||
            filterLoading ||
            (
                !validMonth &&
                !isAllMonths
            )
        ) {
            return;
        }

        if (
            filters.kendala.length > 0 &&
            !filters.kendala.includes(
                selectedKendala,
            )
        ) {
            setSelectedKendala(
                undefined,
            );
        }

    }, [
        filterLoading,
        filters.kendala,
        selectedKendala,
        validMonth,
        isAllMonths,
    ]);


    /* ======================================================
     * LOAD DASHBOARD KPI
     * ====================================================== */

    useEffect(() => {

        if (
            !validMonth &&
            !isAllMonths
        ) {

            setDashboard(
                EMPTY_DASHBOARD,
            );

            setLoading(
                false,
            );

            return;
        }


        let cancelled = false;


        const loadDashboard =
            async () => {

                try {

                    setLoading(
                        true,
                    );

                    const result =
                        await getDlpdDashboard(
                            customerType,
                            validMonth,
                            {
                                unitup:
                                    selectedUnit,

                                status:
                                    selectedStatus,

                                inspection_status:
                                    selectedInspectionStatus,

                                dlpd_repeat:
                                    customerType ===
                                    "pascabayar"
                                        ? selectedRepeat
                                        : undefined,

                                kendala:
                                    selectedKendala,
                            },
                        );

                    if (
                        !cancelled
                    ) {

                        setPageError(
                            null,
                        );

                        setDashboard(
                            result ??
                                EMPTY_DASHBOARD,
                        );
                    }

                } catch (err) {

                    console.error(
                        "Failed to load DLPD dashboard:",
                        err,
                    );

                    if (
                        !cancelled
                    ) {

                        setPageError(
                            "Gagal memuat KPI DLPD. Periksa status backend dan dataset DLPD.",
                        );

                        setDashboard(
                            EMPTY_DASHBOARD,
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


        loadDashboard();


        return () => {
            cancelled = true;
        };

    }, [
        customerType,
        validMonth,
        isAllMonths,
        selectedUnit,
        selectedStatus,
        selectedInspectionStatus,
        selectedRepeat,
        selectedKendala,
    ]);


    /* ======================================================
     * LOAD MAP
     * ====================================================== */

    useEffect(() => {

        if (
            !validMonth &&
            !isAllMonths
        ) {

            setMapPoints([]);

            setMapStats(
                EMPTY_MAP_STATS,
            );

            setMapError(
                undefined,
            );

            setMapLoading(
                false,
            );

            return;
        }


        let cancelled = false;


        const loadMap =
            async () => {

                try {

                    setMapLoading(
                        true,
                    );

                    setMapError(
                        undefined,
                    );


                    const result =
                        await getDlpdMapPoints(
                            customerType,
                            validMonth,
                            {
                                unitup:
                                    selectedUnit,

                                status:
                                    selectedStatus,

                                inspection_status:
                                    selectedInspectionStatus,

                                dlpd_repeat:
                                    customerType ===
                                    "pascabayar"
                                        ? selectedRepeat
                                        : undefined,

                                kendala:
                                    selectedKendala,
                            },
                            100_000,
                        );


                    if (
                        cancelled
                    ) {
                        return;
                    }


                    const validPoints =
                        Array.isArray(
                            result?.points,
                        )
                            ? result.points.filter(
                                  (
                                      point,
                                  ) =>
                                      Number.isFinite(
                                          Number(
                                              point.latitude,
                                          ),
                                      ) &&
                                      Number.isFinite(
                                          Number(
                                              point.longitude,
                                          ),
                                      ),
                              )
                            : [];


                    setMapPoints(
                        validPoints,
                    );


                    setMapStats({

                        total:
                            Number(
                                result?.total ??
                                    0,
                            ),

                        location_matched:
                            Number(
                                result?.location_matched ??
                                    0,
                            ),

                        mapped:
                            Number(
                                result?.mapped ??
                                    0,
                            ),

                        unmapped:
                            Number(
                                result?.unmapped ??
                                    0,
                            ),
                    });

                } catch (err) {

                    console.error(
                        "Failed to load DLPD map:",
                        err,
                    );


                    if (
                        !cancelled
                    ) {

                        setMapPoints([]);

                        setMapStats(
                            EMPTY_MAP_STATS,
                        );

                        setMapError(
                            "Gagal memuat data peta.",
                        );
                    }

                } finally {

                    if (
                        !cancelled
                    ) {

                        setMapLoading(
                            false,
                        );
                    }
                }
            };


        loadMap();


        return () => {
            cancelled = true;
        };

    }, [
        customerType,
        validMonth,
        isAllMonths,
        selectedUnit,
        selectedStatus,
        selectedInspectionStatus,
        selectedRepeat,
        selectedKendala,
    ]);


    /* ======================================================
     * CUSTOMER TYPE CHANGE
     * ====================================================== */

    const handleCustomerTypeChange =
        (
            type: CustomerType,
        ) => {

            if (
                type ===
                customerType
            ) {
                return;
            }


            setSelectedUnit(
                undefined,
            );

            setSelectedStatus(
                undefined,
            );

            setSelectedInspectionStatus(
                undefined,
            );

            setSelectedRepeat(
                undefined,
            );

            setSelectedKendala(
                undefined,
            );

            setSelectedIdpel(
                undefined,
            );

            setMapPoints([]);

            setMapStats(
                EMPTY_MAP_STATS,
            );

            setMapError(
                undefined,
            );

            setFilters(
                EMPTY_FILTERS,
            );

            setDashboard(
                EMPTY_DASHBOARD,
            );


            /**
             * Kalau cache tipe baru sudah tersedia,
             * gunakan bulan terbaru.
             *
             * Kalau user sedang berada pada Semua Bulan,
             * pertahankan Semua Bulan.
             */
            const cachedMonths =
                monthCache[type] ?? [];

            if (
                month === ALL_MONTHS
            ) {

                setMonth(
                    ALL_MONTHS,
                );

            } else if (
                cachedMonths.length > 0
            ) {

                setMonth(
                    cachedMonths[
                        cachedMonths.length -
                            1
                    ].month_key,
                );

            } else {

                setMonth(
                    undefined,
                );
            }


            setMonthLoading(
                cachedMonths.length === 0,
            );


            setCustomerType(
                type,
            );
        };


    /* ======================================================
     * MONTH CHANGE
     * ====================================================== */

    const handleMonthChange =
        (
            value: string,
        ) => {

            /**
             * Mode Semua Bulan.
             */
            if (
                value ===
                ALL_MONTHS
            ) {

                setSelectedUnit(
                    undefined,
                );

                setSelectedStatus(
                    undefined,
                );

                setSelectedInspectionStatus(
                    undefined,
                );

                setSelectedRepeat(
                    undefined,
                );

                setSelectedKendala(
                    undefined,
                );

                setSelectedIdpel(
                    undefined,
                );

                setMapPoints([]);

                setMapStats(
                    EMPTY_MAP_STATS,
                );

                setMapError(
                    undefined,
                );

                setDashboard(
                    EMPTY_DASHBOARD,
                );

                setMonth(
                    ALL_MONTHS,
                );

                return;
            }


            /**
             * Abaikan placeholder.
             */
            if (
                value === ""
            ) {
                return;
            }


            if (
                !isValidMonthKey(
                    value,
                )
            ) {
                return;
            }


            const exists =
                currentMonths.some(
                    (
                        item,
                    ) =>
                        item.month_key ===
                        value,
                );


            if (
                !exists
            ) {
                return;
            }


            if (
                value === month
            ) {
                return;
            }


            /**
             * Semua filter periode sebelumnya
             * dibersihkan ketika pindah periode.
             */
            setSelectedUnit(
                undefined,
            );

            setSelectedStatus(
                undefined,
            );

            setSelectedInspectionStatus(
                undefined,
            );

            setSelectedRepeat(
                undefined,
            );

            setSelectedKendala(
                undefined,
            );

            setSelectedIdpel(
                undefined,
            );

            setMapPoints([]);

            setMapStats(
                EMPTY_MAP_STATS,
            );

            setMapError(
                undefined,
            );

            setDashboard(
                EMPTY_DASHBOARD,
            );

            setMonth(
                value,
            );
        };


    /* ======================================================
     * UNIT CHANGE
     * ====================================================== */

    const handleUnitChange =
        (
            value: string,
        ) => {

            setSelectedUnit(
                value ||
                    undefined,
            );

            setSelectedIdpel(
                undefined,
            );
        };


    /* ======================================================
     * STATUS CHANGE
     * ====================================================== */

    const handleStatusChange =
        (
            value: string,
        ) => {

            setSelectedStatus(
                value ||
                    undefined,
            );

            setSelectedIdpel(
                undefined,
            );
        };


    /* ======================================================
     * INSPECTION STATUS CHANGE
     * ====================================================== */

    const handleInspectionStatusChange =
        (
            value: string,
        ) => {

            setSelectedInspectionStatus(
                value ||
                    undefined,
            );

            setSelectedIdpel(
                undefined,
            );
        };


    /* ======================================================
     * REPEAT CHANGE
     * ====================================================== */

    const handleRepeatChange = (
        value: string,
    ) => {

        setSelectedRepeat(
            value ||
                undefined,
        );

        setSelectedIdpel(
            undefined,
        );
    };


    /* ======================================================
     * KENDALA CHANGE
     * ====================================================== */

    const handleKendalaChange =
        (
            value: string,
        ) => {

            setSelectedKendala(
                value ||
                    undefined,
            );

            setSelectedIdpel(
                undefined,
            );
        };


    /* ======================================================
     * SELECTED CUSTOMER COORDINATE
     * ====================================================== */

    /**
     * Ambil koordinat customer yang sedang dipilih dari data titik peta.
     *
     * Endpoint map sudah mengembalikan latitude/longitude customer,
     * sehingga tombol Google Maps tidak perlu melakukan request tambahan.
     */
    const selectedMapPoint = useMemo(() => {
        if (!selectedIdpel) {
            return undefined;
        }

        return mapPoints.find(
            (point) =>
                String(point.idpel) ===
                String(selectedIdpel),
        );
    }, [mapPoints, selectedIdpel]);

    const selectedLatitude = Number(
        selectedMapPoint?.latitude,
    );

    const selectedLongitude = Number(
        selectedMapPoint?.longitude,
    );

    const hasSelectedCoordinate =
        Number.isFinite(selectedLatitude) &&
        Number.isFinite(selectedLongitude);

    /**
     * Open the selected customer in Google Maps.
     *
     * Priority:
     * 1. Explicit google_maps_url returned by the map API.
     * 2. Exact latitude/longitude from the map point.
     * 3. IDPEL search fallback.
     *
     * The fallback is intentional: a customer can exist in the customer
     * table/detail endpoint even when that customer has no valid coordinate
     * in the map dataset.
     */
    const selectedGoogleMapsUrl = useMemo(() => {
        if (!selectedIdpel) {
            return undefined;
        }

        const point = selectedMapPoint as
            | (DlpdMapPoint & {
                  google_maps_url?: string | null;
              })
            | undefined;

        const explicitUrl =
            typeof point?.google_maps_url === "string" &&
            point.google_maps_url.trim() !== ""
                ? point.google_maps_url.trim()
                : undefined;

        if (explicitUrl) {
            return explicitUrl;
        }

        if (hasSelectedCoordinate) {
            return (
                "https://www.google.com/maps/search/?api=1&query=" +
                encodeURIComponent(
                    `${selectedLatitude},${selectedLongitude}`,
                )
            );
        }

        /**
         * Last-resort fallback. This does not require coordinates and still
         * gives the user a direct Google Maps destination based on IDPEL.
         */
        return (
            "https://www.google.com/maps/search/?api=1&query=" +
            encodeURIComponent(`IDPEL ${selectedIdpel}`)
        );
    }, [
        hasSelectedCoordinate,
        selectedIdpel,
        selectedLatitude,
        selectedLongitude,
        selectedMapPoint,
    ]);

    const handleOpenSelectedCustomerMaps = () => {
        if (!selectedGoogleMapsUrl) {
            return;
        }

        window.open(
            selectedGoogleMapsUrl,
            "_blank",
            "noopener,noreferrer",
        );
    };

    /* ======================================================
     * CURRENT MONTH LABEL
     * ====================================================== */

    const currentMonthLabel =
        useMemo(
            () => {

                if (
                    isAllMonths
                ) {
                    return "Semua Bulan";
                }

                const found =
                    currentMonths.find(
                        (
                            item,
                        ) =>
                            item.month_key ===
                            validMonth,
                    );

                return (
                    found?.label ??
                    (
                        validMonth
                            ? monthKeyToLabel(
                                  validMonth,
                              )
                            : "-"
                    )
                );
            },
            [
                currentMonths,
                validMonth,
                isAllMonths,
            ],
        );


    /* ======================================================
     * RENDER
     * ====================================================== */

    return (
        <div className="dlpd-page">

            {/* ==================================================
             * HEADER
             * ================================================== */}

            <div className="page-header">

                <div>

                    <h1>
                        DLPD Monitoring
                    </h1>

                    <p>
                        Monitoring pelanggan
                        DLPD Prabayar &
                        Pascabayar
                    </p>

                </div>

            </div>


            {pageError && (
                <div
                    role="alert"
                    style={{
                        marginBottom: 16,
                        padding: "12px 16px",
                        borderRadius: 10,
                        border:
                            "1px solid #7f1d1d",
                        background:
                            "#3f1418",
                        color:
                            "#fecaca",
                    }}
                >
                    {pageError}
                </div>
            )}


            {/* ==================================================
             * CUSTOMER TYPE + PERIOD
             * ================================================== */}

            <div className="toolbar">

                <div className="radio-group">

                    <label>

                        <input
                            type="radio"
                            name="customer-type"
                            checked={
                                customerType ===
                                "prabayar"
                            }
                            onChange={() =>
                                handleCustomerTypeChange(
                                    "prabayar",
                                )
                            }
                        />

                        Prabayar

                    </label>


                    <label>

                        <input
                            type="radio"
                            name="customer-type"
                            checked={
                                customerType ===
                                "pascabayar"
                            }
                            onChange={() =>
                                handleCustomerTypeChange(
                                    "pascabayar",
                                )
                            }
                        />

                        Pascabayar

                    </label>

                </div>


                <div className="period-context">

                    Periode analisis:{" "}

                    <strong>
                        {currentMonthLabel}
                    </strong>

                    {customerType ===
                        "pascabayar" && (
                        <span>
                            {" "}
                            · repeat lintas
                            6 periode
                        </span>
                    )}

                </div>

            </div>


            {/* ==================================================
             * KPI
             * ================================================== */}

            <div className="kpi-grid">

                <div className="kpi-card">

                    <span>
                        Total Target
                    </span>

                    <h2>
                        {loading
                            ? "-"
                            : dashboard.total_target.toLocaleString()}
                    </h2>

                </div>


                <div className="kpi-card">

                    <span>
                        Normal
                    </span>

                    <h2>
                        {loading
                            ? "-"
                            : dashboard.normal.toLocaleString()}
                    </h2>

                </div>


                <div className="kpi-card">

                    <span>
                        Temuan
                    </span>

                    <h2>
                        {loading
                            ? "-"
                            : dashboard.temuan.toLocaleString()}
                    </h2>

                </div>


                <div className="kpi-card">

                    <span>
                        Belum Periksa
                    </span>

                    <h2>
                        {loading
                            ? "-"
                            : dashboard.belum_periksa.toLocaleString()}
                    </h2>

                </div>

            </div>


            {/* ==================================================
             * FILTER
             * ================================================== */}

            <div className="filter-bar">

                {/* ============================
                 * BULAN
                 * ============================ */}

                <select
                    className="month-filter"
                    value={
                        month ?? ""
                    }
                    disabled={
                        monthLoading
                    }
                    onChange={(e) =>
                        handleMonthChange(
                            e.target.value,
                        )
                    }
                >

                    <option value="">
                        {monthLoading
                            ? "Memuat Bulan..."
                            : "Pilih Bulan"}
                    </option>


                    {/* =========================================
                     * SEMUA BULAN
                     * ========================================= */}

                    <option
                        value={
                            ALL_MONTHS
                        }
                    >
                        Semua Bulan
                    </option>


                    {currentMonths.map(
                        (
                            item,
                        ) => (
                            <option
                                key={
                                    item.month_key
                                }
                                value={
                                    item.month_key
                                }
                            >
                                {
                                    item.label
                                }
                            </option>
                        ),
                    )}

                </select>


                {/* ============================
                 * UNIT
                 * ============================ */}

                <select
                    value={
                        selectedUnit ??
                        ""
                    }
                    disabled={
                        filterLoading ||
                        (
                            !validMonth &&
                            !isAllMonths
                        )
                    }
                    onChange={(e) =>
                        handleUnitChange(
                            e.target.value,
                        )
                    }
                >

                    <option value="">
                        Semua Unit
                    </option>

                    {filters.unitup.map(
                        (
                            unit,
                        ) => (
                            <option
                                key={unit}
                                value={unit}
                            >
                                {unit}
                            </option>
                        ),
                    )}

                </select>


                {/* ============================
                 * STATUS
                 * ============================ */}

                <select
                    value={
                        selectedStatus ??
                        ""
                    }
                    disabled={
                        filterLoading ||
                        (
                            !validMonth &&
                            !isAllMonths
                        )
                    }
                    onChange={(e) =>
                        handleStatusChange(
                            e.target.value,
                        )
                    }
                >

                    <option value="">
                        Semua Status
                    </option>

                    {filters.status.map(
                        (
                            status,
                        ) => (
                            <option
                                key={status}
                                value={status}
                            >
                                {status}
                            </option>
                        ),
                    )}

                </select>


                {/* ============================
                 * STATUS PEMERIKSAAN
                 * ============================ */}

                <select
                    value={
                        selectedInspectionStatus ??
                        ""
                    }
                    disabled={
                        filterLoading ||
                        (
                            !validMonth &&
                            !isAllMonths
                        )
                    }
                    onChange={(e) =>
                        handleInspectionStatusChange(
                            e.target.value,
                        )
                    }
                >

                    <option value="">
                        Semua Status Pemeriksaan
                    </option>

                    {filters.inspection_status.map(
                        (
                            inspectionStatus,
                        ) => (
                            <option
                                key={
                                    inspectionStatus
                                }
                                value={
                                    inspectionStatus
                                }
                            >
                                {
                                    inspectionStatus
                                }
                            </option>
                        ),
                    )}

                </select>


                {/* ============================
                 * REPEAT
                 * ============================ */}

                {customerType ===
                    "pascabayar" && (
                    <select
                        value={
                            selectedRepeat ??
                            ""
                        }
                        disabled={
                            filterLoading ||
                            (
                                !validMonth &&
                                !isAllMonths
                            )
                        }
                        onChange={(e) =>
                            handleRepeatChange(
                                e.target.value,
                            )
                        }
                    >

                        <option value="">
                            Semua Perulangan
                        </option>

                        {filters.dlpd_repeat.map(
                            (
                                repeat,
                            ) => (
                                <option
                                    key={
                                        repeat
                                    }
                                    value={
                                        repeat
                                    }
                                >
                                    {repeat}
                                </option>
                            ),
                        )}

                    </select>
                )}


                {/* ============================
                 * KENDALA
                 * ============================ */}

                <select
                    value={
                        selectedKendala ??
                        ""
                    }
                    disabled={
                        filterLoading ||
                        (
                            !validMonth &&
                            !isAllMonths
                        )
                    }
                    onChange={(e) =>
                        handleKendalaChange(
                            e.target.value,
                        )
                    }
                >

                    <option value="">
                        Semua Kendala
                    </option>

                    {currentKendalaOptions.map(
                        (
                            option,
                        ) => (
                            <option
                                key={
                                    option.value
                                }
                                value={
                                    option.value
                                }
                            >
                                {
                                    option.label
                                }
                            </option>
                        ),
                    )}

                </select>

            </div>


            {/* ==================================================
             * MAP
             * ================================================== */}

            <section className="panel">

                <div className="panel-header">
                    Peta Lokasi Pelanggan
                </div>


                <div
                    className="panel-body"
                    style={{
                        padding: 0,
                    }}
                >

                    <div
                        style={{
                            display:
                                "grid",
                            gridTemplateColumns:
                                "repeat(4, minmax(0, 1fr))",
                            gap: 12,
                            padding:
                                "16px 20px",
                            borderBottom:
                                "1px solid #334155",
                        }}
                    >

                        <div>

                            <span
                                style={{
                                    display:
                                        "block",
                                    fontSize: 12,
                                    color:
                                        "#94a3b8",
                                }}
                            >
                                Total
                            </span>

                            <strong
                                style={{
                                    fontSize: 20,
                                    color:
                                        "#f8fafc",
                                }}
                            >
                                {mapLoading
                                    ? "-"
                                    : mapStats.total.toLocaleString()}
                            </strong>

                        </div>


                        <div>

                            <span
                                style={{
                                    display:
                                        "block",
                                    fontSize: 12,
                                    color:
                                        "#94a3b8",
                                }}
                            >
                                Location Matched
                            </span>

                            <strong
                                style={{
                                    fontSize: 20,
                                    color:
                                        "#f8fafc",
                                }}
                            >
                                {mapLoading
                                    ? "-"
                                    : mapStats.location_matched.toLocaleString()}
                            </strong>

                        </div>


                        <div>

                            <span
                                style={{
                                    display:
                                        "block",
                                    fontSize: 12,
                                    color:
                                        "#94a3b8",
                                }}
                            >
                                Mapped
                            </span>

                            <strong
                                style={{
                                    fontSize: 20,
                                    color:
                                        "#22c55e",
                                }}
                            >
                                {mapLoading
                                    ? "-"
                                    : mapStats.mapped.toLocaleString()}
                            </strong>

                        </div>


                        <div>

                            <span
                                style={{
                                    display:
                                        "block",
                                    fontSize: 12,
                                    color:
                                        "#94a3b8",
                                }}
                            >
                                Unmapped
                            </span>

                            <strong
                                style={{
                                    fontSize: 20,
                                    color:
                                        "#f97316",
                                }}
                            >
                                {mapLoading
                                    ? "-"
                                    : mapStats.unmapped.toLocaleString()}
                            </strong>

                        </div>

                    </div>


                    {mapError ? (

                        <div
                            style={{
                                padding: 40,
                                textAlign:
                                    "center",
                                color:
                                    "#f87171",
                            }}
                        >
                            {mapError}
                        </div>

                    ) : mapLoading ? (

                        <div
                            style={{
                                padding: 40,
                                textAlign:
                                    "center",
                                color:
                                    "#94a3b8",
                            }}
                        >
                            Memuat peta...
                        </div>

                    ) : mapPoints.length ===
                      0 ? (

                        <div
                            style={{
                                padding: 40,
                                textAlign:
                                    "center",
                                color:
                                    "#94a3b8",
                            }}
                        >
                            Tidak ada pelanggan
                            dengan koordinat yang
                            dapat ditampilkan pada
                            peta.
                        </div>

                    ) : (

                        <DlpdMap
                            points={
                                mapPoints
                            }
                            height={
                                520
                            }
                        />

                    )}

                </div>

            </section>


            {/* ==================================================
             * DASHBOARD + DETAIL
             * ================================================== */}

            <div className="content-grid">

                <section className="panel">

                    <div className="panel-header">
                        Dashboard ULP
                    </div>

                    <div className="panel-body">

                        <DlpdUnitTable
                            customerType={
                                customerType
                            }
                            month={
                                validMonth
                            }
                            filters={{
                                unitup:
                                    selectedUnit,

                                status:
                                    selectedStatus,

                                inspection_status:
                                    selectedInspectionStatus,

                                dlpd_repeat:
                                    customerType ===
                                    "pascabayar"
                                        ? selectedRepeat
                                        : undefined,

                                kendala:
                                    selectedKendala,
                            }}
                            onSelect={
                                handleUnitChange
                            }
                        />

                    </div>

                </section>


                <section className="panel">

                    <div className="panel-header">
                        Detail Pelanggan
                    </div>

                    <div className="panel-body">

                        {selectedIdpel && (
                            <div
                                style={{
                                    display: "flex",
                                    justifyContent: "flex-end",
                                    marginBottom: 12,
                                }}
                            >
                                <button
                                    type="button"
                                    onClick={
                                        handleOpenSelectedCustomerMaps
                                    }
                                    disabled={
                                        !selectedGoogleMapsUrl
                                    }
                                    title={
                                        hasSelectedCoordinate
                                            ? "Buka lokasi pelanggan di Google Maps"
                                            : "Buka pencarian IDPEL pelanggan di Google Maps"
                                    }
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 8,
                                        border: "1px solid #2563eb",
                                        borderRadius: 8,
                                        padding:
                                            "9px 14px",
                                        background:
                                            selectedGoogleMapsUrl
                                                ? "#1d4ed8"
                                                : "#334155",
                                        color:
                                            selectedGoogleMapsUrl
                                                ? "#ffffff"
                                                : "#94a3b8",
                                        fontSize: 13,
                                        fontWeight: 600,
                                        cursor:
                                            selectedGoogleMapsUrl
                                                ? "pointer"
                                                : "not-allowed",
                                        opacity:
                                            selectedGoogleMapsUrl
                                                ? 1
                                                : 0.7,
                                    }}
                                >
                                    <span
                                        aria-hidden="true"
                                    >
                                        📍
                                    </span>
                                    Buka di Google Maps
                                </button>
                            </div>
                        )}

                        {selectedIdpel && (
                            <div
                                style={{
                                    marginBottom: 12,
                                    padding: "10px 12px",
                                    borderRadius: 8,
                                    background: "#111827",
                                    border: "1px solid #334155",
                                    color: "#cbd5e1",
                                    fontSize: 13,
                                }}
                            >
                                Pelanggan dipilih:{" "}
                                <strong
                                    style={{
                                        color: "#f8fafc",
                                    }}
                                >
                                    {selectedIdpel}
                                </strong>
                            </div>
                        )}

                        <DlpdDetail
                            idpel={
                                selectedIdpel
                            }
                            customerType={
                                customerType
                            }
                            month={
                                validMonth
                            }
                        />

                        {selectedIdpel &&
                            !hasSelectedCoordinate && (
                                <div
                                    style={{
                                        marginTop: 10,
                                        padding:
                                            "10px 12px",
                                        borderRadius: 8,
                                        border:
                                            "1px solid #334155",
                                        background:
                                            "#0f172a",
                                        color:
                                            "#94a3b8",
                                        fontSize: 12,
                                    }}
                                >
                                    Koordinat pelanggan belum tersedia
                                    pada data peta. Tombol Google Maps
                                    akan membuka pencarian berdasarkan
                                    IDPEL sebagai fallback.
                                </div>
                            )}

                    </div>

                </section>

            </div>


            {/* ==================================================
             * CUSTOMER
             * ================================================== */}

            <section className="panel">

                <div className="panel-header">
                    Daftar Pelanggan
                </div>

                <div className="panel-body">

                    <DlpdCustomerTable
                        customerType={
                            customerType
                        }
                        month={
                            validMonth
                        }
                        filters={{
                            unitup:
                                selectedUnit,

                            status:
                                selectedStatus,

                            inspection_status:
                                selectedInspectionStatus,

                            dlpd_repeat:
                                customerType ===
                                "pascabayar"
                                    ? selectedRepeat
                                    : undefined,

                            kendala:
                                selectedKendala,
                        }}
                        onSelect={
                            setSelectedIdpel
                        }
                    />

                </div>

            </section>

        </div>
    );
}