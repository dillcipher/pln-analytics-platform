import "./DlpdDetail.css";
import {
    useEffect,
    useState,
    type ReactNode,
} from "react";

import { getDlpdCustomerDetail } from "../../api/dlpd";

import type {
    CustomerType,
    DlpdCustomerDetail,
} from "../../api/dlpd";


interface Props {
    idpel?: string;
    customerType: CustomerType;
    month?: string;
}


/* ==========================================================
 * HELPERS
 * ========================================================== */

function text(
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


function formatDaya(
    value: unknown,
): string {
    if (
        value === null ||
        value === undefined ||
        String(value).trim() === ""
    ) {
        return "-";
    }

    const numeric = Number(value);

    if (!Number.isFinite(numeric)) {
        return String(value);
    }

    return `${numeric.toLocaleString(
        "id-ID",
    )} VA`;
}


function isBelumPeriksa(
    value: unknown,
): boolean {
    return String(value ?? "")
        .toLowerCase()
        .includes("belum");
}


function getBadgeClass(
    value: unknown,
): string {
    const normalized = String(
        value ?? "",
    ).trim().toLowerCase();

    if (
        normalized.includes(
            "belum",
        )
    ) {
        return "detail-badge warning";
    }

    if (
        normalized.includes(
            "temuan",
        )
    ) {
        return "detail-badge warning";
    }

    if (
        normalized.includes(
            "normal",
        ) ||
        normalized.includes(
            "sudah",
        ) ||
        normalized.includes(
            "lunas",
        )
    ) {
        return "detail-badge success";
    }

    return "detail-badge muted";
}


/* ==========================================================
 * FIELD
 * ========================================================== */

function DetailField({
    label,
    children,
    className = "",
}: {
    label: string;
    children: ReactNode;
    className?: string;
}) {
    return (
        <div
            className={`detail-field ${className}`}
        >
            <span className="detail-field-label">
                {label}
            </span>

            <strong className="detail-field-value">
                {children}
            </strong>
        </div>
    );
}


/* ==========================================================
 * EMPTY STATE
 * ========================================================== */

function EmptyDetail({
    title,
    description,
}: {
    title: string;
    description?: string;
}) {
    return (
        <div className="detail-empty">
            <div className="detail-empty-icon">
                ⓘ
            </div>

            <h3>{title}</h3>

            {description && (
                <p>
                    {description}
                </p>
            )}
        </div>
    );
}


/* ==========================================================
 * MAIN COMPONENT
 * ========================================================== */

export default function DlpdDetail({
    idpel,
    customerType,
    month,
}: Props) {
    const [
        data,
        setData,
    ] = useState<
        DlpdCustomerDetail | null
    >(null);

    const [
        loading,
        setLoading,
    ] = useState(false);

    const [
        error,
        setError,
    ] = useState<
        string | undefined
    >();


    /* ======================================================
     * LOAD DETAIL
     * ====================================================== */

    useEffect(() => {
        if (!idpel) {
            setData(null);
            setError(undefined);
            setLoading(false);

            return;
        }

        let cancelled = false;

        setLoading(true);
        setError(undefined);

        getDlpdCustomerDetail(
            idpel,
            customerType,
            month,
        )
            .then((result) => {
                if (
                    cancelled
                ) {
                    return;
                }

                setData(result);
            })
            .catch((exception) => {
                console.error(
                    "Failed to load DLPD customer detail:",
                    exception,
                );

                if (
                    cancelled
                ) {
                    return;
                }

                setData(null);

                setError(
                    "Detail pelanggan gagal dimuat.",
                );
            })
            .finally(() => {
                if (
                    cancelled
                ) {
                    return;
                }

                setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [
        idpel,
        customerType,
        month,
    ]);


    /* ======================================================
     * EMPTY
     * ====================================================== */

    if (!idpel) {
        return (
            <EmptyDetail
                title="Belum ada pelanggan dipilih"
                description="Klik baris pelanggan pada daftar untuk melihat detail."
            />
        );
    }


    /* ======================================================
     * LOADING
     * ====================================================== */

    if (loading) {
        return (
            <div className="detail-empty">
                <div className="detail-loading">
                    <span />
                    <span />
                    <span />
                </div>

                <h3>
                    Memuat detail pelanggan...
                </h3>

                <p>
                    IDPEL:{" "}
                    <strong>
                        {idpel}
                    </strong>
                </p>
            </div>
        );
    }


    /* ======================================================
     * ERROR / NOT FOUND
     * ====================================================== */

    if (
        error ||
        !data?.customer
    ) {
        return (
            <EmptyDetail
                title={
                    error ??
                    "Data pelanggan tidak ditemukan"
                }
                description={`IDPEL: ${idpel}`}
            />
        );
    }


    const customer =
        data.customer;

    const latitude =
        data.latitude ??
        customer.latitude;

    const longitude =
        data.longitude ??
        customer.longitude;

    const hasExactLocation =
        Number.isFinite(
            Number(latitude),
        ) &&
        Number.isFinite(
            Number(longitude),
        );

    const inspected =
        !isBelumPeriksa(
            customer.status,
        );

    const inspectionLabel =
        inspected
            ? "Sudah Periksa"
            : "Belum Periksa";


    /* ======================================================
     * DETAIL FIELDS
     * ====================================================== */

    const fields: Array<
        [
            string,
            ReactNode,
        ]
    > = [
        [
            "IDPEL",
            text(
                customer.idpel,
            ),
        ],

        [
            "Nama",
            text(
                customer.nama,
            ),
        ],

        [
            "UNITUPI",
            text(
                customer.unitupi,
            ),
        ],

        [
            "UNITAP",
            text(
                customer.unitap,
            ),
        ],

        [
            "UNITUP",
            text(
                customer.unitup,
            ),
        ],

        [
            "Status Pemeriksaan",
            <span
                className={getBadgeClass(
                    inspectionLabel,
                )}
            >
                {inspectionLabel}
            </span>,
        ],

        [
            "Hasil",
            <span
                className={getBadgeClass(
                    customer.status,
                )}
            >
                {text(
                    customer.status,
                )}
            </span>,
        ],

        [
            "Tarif",
            text(
                customer.tariff,
            ),
        ],

        [
            "Daya",
            formatDaya(
                customer.daya,
            ),
        ],

        [
            "Perulangan",
            <span
                className="detail-repeat-value"
            >
                {text(
                    customer.dlpd_repeat,
                )}
            </span>,
        ],

        [
            "Kategori",
            text(
                customer.kategori,
            ),
        ],

        [
            "Kendala / Keterangan",
            text(
                customer.keterangan ??
                    customer.alasan,
            ),
        ],

        [
            "Alamat",
            text(
                customer.alamat,
            ),
        ],

        [
            "Lokasi",
            hasExactLocation
                ? `${Number(latitude).toFixed(6)}, ${Number(
                      longitude,
                  ).toFixed(6)}`
                : "Koordinat belum tersedia",
        ],

        [
            "Petugas",
            text(
                customer.petugas,
            ),
        ],

        [
            "Regu",
            text(
                customer.regu,
            ),
        ],

        [
            "Waktu Periksa",
            text(
                customer.waktu_periksa,
            ),
        ],

        [
            "Catatan",
            text(
                customer.catatan,
            ),
        ],
    ];


    /* ======================================================
     * RENDER
     * ====================================================== */

    return (
        <div className="detail-content">

            {/* ==================================================
             * SELECTED CUSTOMER
             * ================================================== */}

            <div className="detail-selected">
                <div className="detail-selected-main">
                    <span className="detail-selected-label">
                        PELANGGAN TERPILIH
                    </span>

                    <div className="detail-selected-id">
                        {text(
                            customer.idpel,
                        )}
                    </div>

                    <div className="detail-selected-name">
                        {text(
                            customer.nama,
                        )}
                    </div>
                </div>

                <div
                    className="detail-selected-status"
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        gap: 8,
                        flexWrap: "wrap",
                    }}
                >
                    <span
                        className={getBadgeClass(
                            inspectionLabel,
                        )}
                    >
                        {inspectionLabel}
                    </span>

                    <span
                        className={getBadgeClass(
                            customer.status,
                        )}
                    >
                        {text(
                            customer.status,
                        )}
                    </span>


                </div>
            </div>


            {/* ==================================================
             * CUSTOMER INFORMATION
             * ================================================== */}

            <section className="detail-section">

                <div className="detail-section-header">
                    <div>
                        <h3>
                            Informasi Pelanggan
                        </h3>

                        <p>
                            Informasi utama pelanggan
                            dan hasil pemeriksaan.
                        </p>
                    </div>
                </div>


                <div className="detail-grid">

                    {fields.map(
                        (
                            [label, value],
                        ) => (
                            <DetailField
                                key={label}
                                label={
                                    label
                                }
                            >
                                {
                                    value
                                }
                            </DetailField>
                        ),
                    )}

                </div>



            </section>


            {/* ==================================================
             * INSPECTION HISTORY
             * ================================================== */}

            <section className="detail-history">

                <div className="detail-history-head">

                    <div>
                        <h3>
                            Riwayat Pemeriksaan
                        </h3>

                        <p>
                            Riwayat pemeriksaan
                            pelanggan terkait.
                        </p>
                    </div>

                    <span className="detail-history-count">
                        {(
                            data
                                .inspection_history
                                ?.length ??
                            0
                        ).toLocaleString(
                            "id-ID",
                        )}{" "}
                        record
                    </span>

                </div>


                {!data
                    .inspection_history
                    ?.length ? (
                    <div className="detail-history-empty">
                        <strong>
                            Belum ada riwayat
                            pemeriksaan.
                        </strong>

                        <span>
                            Tidak terdapat record
                            pemeriksaan untuk
                            pelanggan ini.
                        </span>
                    </div>
                ) : (
                    <div className="detail-history-scroll">

                        <table className="detail-history-table">

                            <thead>
                                <tr>
                                    <th>
                                        Waktu
                                    </th>

                                    <th>
                                        Hasil
                                    </th>

                                    <th>
                                        Petugas
                                    </th>

                                    <th>
                                        Regu
                                    </th>

                                    <th>
                                        Catatan
                                    </th>

                                    <th>
                                        Tindak Lanjut
                                    </th>
                                </tr>
                            </thead>


                            <tbody>

                                {data.inspection_history.map(
                                    (
                                        record,
                                        index,
                                    ) => {
                                        const rowKey =
                                            `${
                                                record.waktu_periksa ??
                                                "row"
                                            }-${index}`;

                                        return (
                                            <tr
                                                key={
                                                    rowKey
                                                }
                                            >

                                                <td>
                                                    {text(
                                                        record.waktu_periksa,
                                                    )}
                                                </td>

                                                <td>
                                                    <span
                                                        className={getBadgeClass(
                                                            record.status,
                                                        )}
                                                    >
                                                        {text(
                                                            record.status,
                                                        )}
                                                    </span>
                                                </td>

                                                <td>
                                                    {text(
                                                        record.petugas,
                                                    )}
                                                </td>

                                                <td>
                                                    {text(
                                                        record.regu,
                                                    )}
                                                </td>

                                                <td
                                                    title={text(
                                                        record.catatan,
                                                    )}
                                                >
                                                    {text(
                                                        record.catatan,
                                                    )}
                                                </td>

                                                <td
                                                    title={text(
                                                        record.tindak_lanjut,
                                                    )}
                                                >
                                                    {text(
                                                        record.tindak_lanjut,
                                                    )}
                                                </td>

                                            </tr>
                                        );
                                    },
                                )}

                            </tbody>

                        </table>

                    </div>
                )}

            </section>

        </div>
    );
}