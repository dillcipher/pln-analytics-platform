import "./DlpdUnitTable.css";

import {
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    getDlpdDashboardUlp,
} from "../../api/dlpd";

import type {
    DlpdDashboardUlp,
} from "../../api/dlpd";


interface Props {
    customerType:
        | "prabayar"
        | "pascabayar";

    month?: string;

    filters?: {
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
    dlpd_repeat?: string;

        /*
         * KENDALA
         */
        kendala?: string;
    };

    onSelect?: (
        unitup: string,
    ) => void;
}


export default function DlpdUnitTable({
    customerType,
    month,
    filters,
    onSelect,
}: Props) {

    /* ======================================================
     * DATA
     * ====================================================== */

    const [
        rows,
        setRows,
    ] = useState<
        DlpdDashboardUlp[]
    >([]);


    const [
        loading,
        setLoading,
    ] = useState<boolean>(
        false,
    );

    const [
        error,
        setError,
    ] = useState<string | null>(
        null,
    );


    /* ======================================================
     * SEARCH
     * ====================================================== */

    const [
        search,
        setSearch,
    ] = useState<string>("");


    /* ======================================================
     * LOAD DASHBOARD ULP
     * ====================================================== */

    useEffect(() => {

        let mounted = true;


        const load = async () => {

            try {

                setLoading(
                    true,
                );
                setError(null);


                const result =
                    await getDlpdDashboardUlp(
                        customerType,
                        month,
                        {
                            /*
                             * UNIT
                             */
                            unitup:
                                filters?.unitup,

                            /*
                             * STATUS HASIL
                             *
                             * NORMAL /
                             * TEMUAN
                             */
                            status:
                                filters?.status,

                            /*
                             * STATUS PEMERIKSAAN
                             *
                             * SUDAH PERIKSA /
                             * BELUM PERIKSA
                             */
                            inspection_status:
                                filters?.inspection_status,

                            dlpd_repeat:
                                customerType === "pascabayar"
                                    ? filters?.dlpd_repeat
                                    : undefined,

                            /*
                             * KENDALA
                             */
                            kendala:
                                filters?.kendala,
                        },
                    );


                if (!mounted) {
                    return;
                }


                setRows(
                    Array.isArray(
                        result,
                    )
                        ? result
                        : [],
                );

            } catch (err) {

                console.error(
                    "Failed to load DLPD ULP dashboard:",
                    err,
                );


                if (mounted) {
                    setRows([]);
                    setError(
                        err instanceof Error
                            ? err.message
                            : "Gagal memuat Dashboard ULP.",
                    );
                }

            } finally {

                if (mounted) {
                    setLoading(
                        false,
                    );
                }
            }
        };


        /*
         * `month` boleh undefined.
         *
         * Undefined berarti "Semua Bulan" dan backend memang
         * mendukung month=None untuk mengambil seluruh periode.
         *
         * Jadi JANGAN menghentikan request ketika month kosong.
         */
        load();


        return () => {
            mounted = false;
        };

    }, [
        customerType,
        month,
        filters?.unitup,
        filters?.status,
        filters?.inspection_status,
        filters?.dlpd_repeat,
        filters?.kendala,
    ]);


    /* ======================================================
     * LOCAL SEARCH
     * ====================================================== */

    const filtered =
        useMemo(() => {

            const keyword =
                search
                    .trim()
                    .toLowerCase();


            if (!keyword) {
                return rows;
            }


            return rows.filter(
                (row) =>
                    row.unitup
                        .toLowerCase()
                        .includes(
                            keyword,
                        ) ||
                    row.unit_name
                        .toLowerCase()
                        .includes(
                            keyword,
                        ),
            );

        }, [
            rows,
            search,
        ]);


    /* ======================================================
     * RENDER
     * ====================================================== */

    return (
        <>

            <div
                className="table-toolbar"
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent:
                        "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                }}
            >

                <input
                    placeholder="Cari ULP..."
                    value={search}
                    onChange={(e) =>
                        setSearch(
                            e.target.value,
                        )
                    }
                />

                {!loading &&
                    filtered.length > 0 && (
                        <span
                            style={{
                                color:
                                    "#64748b",
                                fontSize: 11,
                            }}
                        >
                            Klik ULP untuk melihat
                            daftar pelanggan
                        </span>
                    )}

            </div>


            {error && (
                <div className="ulp-dashboard-error">
                    {error}
                </div>
            )}

            <table>

                <thead>

                    <tr>

                        <th>
                            ULP
                        </th>

                        <th>
                            Total
                        </th>

                        <th>
                            Normal
                        </th>

                        <th>
                            Temuan
                        </th>

                        <th>
                            Belum
                        </th>

                        <th>
                            %
                        </th>

                        {customerType ===
                            "pascabayar" && (
                            <>
                                <th>
                                    KWH &lt; 40
                                </th>

                                <th>
                                    KWH = 0
                                </th>
                            </>
                        )}

                    </tr>

                </thead>


                <tbody>

                    {loading && (

                        <tr>

                            <td
                                colSpan={
                                    customerType ===
                                        "pascabayar"
                                        ? 8
                                        : 6
                                }
                                style={{
                                    textAlign:
                                        "center",
                                }}
                            >
                                Loading...
                            </td>

                        </tr>

                    )}


                    {!loading &&
                        filtered.length ===
                            0 && (

                        <tr>

                            <td
                                colSpan={
                                    customerType ===
                                        "pascabayar"
                                        ? 8
                                        : 6
                                }
                                style={{
                                    textAlign:
                                        "center",
                                }}
                            >
                                Tidak ada data
                            </td>

                        </tr>

                    )}


                    {!loading &&
                        filtered.map(
                            (
                                row,
                            ) => (

                            <tr
                                key={
                                    row.unitup
                                }
                                onClick={() =>
                                    onSelect?.(
                                        row.unitup,
                                    )
                                }
                                onKeyDown={(
                                    event,
                                ) => {
                                    if (
                                        event.key ===
                                            "Enter" ||
                                        event.key ===
                                            " "
                                    ) {
                                        event.preventDefault();

                                        onSelect?.(
                                            row.unitup,
                                        );
                                    }
                                }}
                                tabIndex={
                                    onSelect
                                        ? 0
                                        : undefined
                                }
                                role={
                                    onSelect
                                        ? "button"
                                        : undefined
                                }
                                aria-label={
                                    onSelect
                                        ? `Buka ULP ${row.unit_name}`
                                        : undefined
                                }
                                style={{
                                    cursor:
                                        onSelect
                                            ? "pointer"
                                            : "default",
                                }}
                            >

                                <td>
                                    <div
                                        style={{
                                            display:
                                                "flex",
                                            alignItems:
                                                "center",
                                            gap: 8,
                                        }}
                                    >
                                        <div>
                                            <div
                                                style={{
                                                    fontWeight:
                                                        600,
                                                }}
                                            >
                                                {
                                                    row.unit_name
                                                }
                                            </div>

                                            <div
                                                style={{
                                                    marginTop:
                                                        2,
                                                    fontSize:
                                                        10,
                                                    color:
                                                        "#64748b",
                                                }}
                                            >
                                                {
                                                    row.unitup
                                                }
                                            </div>
                                        </div>

                                        {onSelect && (
                                            <span
                                                aria-hidden="true"
                                                style={{
                                                    marginLeft:
                                                        "auto",
                                                    color:
                                                        "#64748b",
                                                    fontSize:
                                                        14,
                                                }}
                                            >
                                                →
                                            </span>
                                        )}
                                    </div>
                                </td>


                                <td>
                                    {row.total.toLocaleString()}
                                </td>


                                <td>
                                    {row.normal.toLocaleString()}
                                </td>


                                <td>
                                    {row.temuan.toLocaleString()}
                                </td>


                                <td>
                                    {row.belum_periksa.toLocaleString()}
                                </td>


                                <td>
                                    {row.percentage.toFixed(
                                        2,
                                    )}
                                    %
                                </td>

                                {customerType ===
                                    "pascabayar" && (
                                    <>
                                        <td>
                                            {(
                                                row.kwh_lt40 ??
                                                0
                                            ).toLocaleString(
                                                "id-ID",
                                            )}
                                        </td>

                                        <td>
                                            {(
                                                row.kwh_zero ??
                                                0
                                            ).toLocaleString(
                                                "id-ID",
                                            )}
                                        </td>
                                    </>
                                )}

                            </tr>

                        ),
                    )}

                </tbody>

            </table>

        </>
    );
}

