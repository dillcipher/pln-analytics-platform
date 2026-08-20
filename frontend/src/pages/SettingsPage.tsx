import { useCallback, useEffect, useState } from "react";
import {
    getSystemHealth,
    refreshWarehouse,
} from "../api/system";

type SystemHealth = {
    status?: string;
    application?: string;
    environment?: string;
};

function formatTime(value: Date | null): string {
    if (!value) {
        return "-";
    }

    return value.toLocaleString("id-ID", {
        dateStyle: "medium",
        timeStyle: "medium",
    });
}

function normalizeStatus(
    health: SystemHealth | undefined,
): "online" | "offline" {
    return health?.status?.toLowerCase() === "ok"
        ? "online"
        : "offline";
}

export default function SettingsPage() {
    const [health, setHealth] =
        useState<SystemHealth | undefined>();

    const [checking, setChecking] =
        useState(true);

    const [refreshing, setRefreshing] =
        useState(false);

    const [message, setMessage] =
        useState("");

    const [messageType, setMessageType] =
        useState<"success" | "error" | "">("");

    const [lastChecked, setLastChecked] =
        useState<Date | null>(null);

    const checkService = useCallback(
        async () => {
            setChecking(true);
            setMessage("");
            setMessageType("");

            try {
                const result =
                    await getSystemHealth();

                setHealth(result);
                setLastChecked(new Date());
            } catch (error) {
                console.error(
                    "Health check failed:",
                    error,
                );

                setHealth(undefined);
                setLastChecked(new Date());

                setMessage(
                    "Backend tidak dapat dihubungi. Pastikan FastAPI aktif dan API URL sudah benar.",
                );

                setMessageType("error");
            } finally {
                setChecking(false);
            }
        },
        [],
    );

    useEffect(() => {
        void checkService();
    }, [checkService]);

    const handleRefreshWarehouse =
        async () => {
            if (refreshing) {
                return;
            }

            setRefreshing(true);
            setMessage("");
            setMessageType("");

            try {
                await refreshWarehouse();

                setMessage(
                    "Warehouse berhasil di-refresh. Dashboard sekarang dapat membaca data terbaru.",
                );

                setMessageType("success");

                await checkService();
            } catch (error) {
                console.error(
                    "Warehouse refresh failed:",
                    error,
                );

                setMessage(
                    "Refresh warehouse gagal. Periksa status backend dan proses ETL.",
                );

                setMessageType("error");
            } finally {
                setRefreshing(false);
            }
        };

    const serviceStatus =
        normalizeStatus(health);

    const serviceLabel =
        checking
            ? "CHECKING"
            : serviceStatus === "online"
                ? "ONLINE"
                : "OFFLINE";

    return (
        <div className="system-page settings-page">

            {/* =====================================================
                PAGE HEADER
            ====================================================== */}

            <div className="system-header">
                <div>
                    <div className="settings-eyebrow">
                        SYSTEM CONFIGURATION
                    </div>

                    <h1>Settings</h1>

                    <p>
                        Status layanan dan standar
                        operasional analytics platform.
                    </p>
                </div>

                <button
                    type="button"
                    className="settings-primary-button"
                    onClick={() =>
                        void checkService()
                    }
                    disabled={checking}
                >
                    {checking
                        ? "Checking..."
                        : "Check Service"}
                </button>
            </div>

            {/* =====================================================
                GLOBAL MESSAGE
            ====================================================== */}

            {message && (
                <div
                    className={`settings-message ${
                        messageType === "success"
                            ? "success"
                            : "error"
                    }`}
                >
                    <div className="settings-message-icon">
                        {messageType === "success"
                            ? "✓"
                            : "!"}
                    </div>

                    <div>
                        <strong>
                            {messageType === "success"
                                ? "Operation completed"
                                : "Service warning"}
                        </strong>

                        <span>
                            {message}
                        </span>
                    </div>
                </div>
            )}

            {/* =====================================================
                APPLICATION + WAREHOUSE
            ====================================================== */}

            <div className="settings-grid">

                {/* APPLICATION STATUS */}

                <section className="system-panel settings-card">
                    <div className="system-panel-head">
                        <div>
                            <h2>
                                Application Status
                            </h2>

                            <p>
                                Status koneksi frontend
                                ke FastAPI.
                            </p>
                        </div>

                        <span
                            className={`service-indicator ${
                                checking
                                    ? "checking"
                                    : serviceStatus
                            }`}
                        >
                            <span className="service-dot" />

                            {serviceLabel}
                        </span>
                    </div>

                    <div className="settings-list">

                        <div>
                            <span>
                                Service
                            </span>

                            <strong
                                className={
                                    serviceStatus ===
                                    "online"
                                        ? "healthy"
                                        : "unhealthy"
                                }
                            >
                                {serviceLabel}
                            </strong>
                        </div>

                        <div>
                            <span>
                                Application
                            </span>

                            <strong>
                                {health?.application ??
                                    "-"}
                            </strong>
                        </div>

                        <div>
                            <span>
                                Environment
                            </span>

                            <strong>
                                {health?.environment ??
                                    "-"}
                            </strong>
                        </div>

                        <div>
                            <span>
                                API Base
                            </span>

                            <strong>
                                /api/v1
                            </strong>
                        </div>

                        <div>
                            <span>
                                Last Checked
                            </span>

                            <strong>
                                {formatTime(
                                    lastChecked,
                                )}
                            </strong>
                        </div>

                    </div>
                </section>

                {/* WAREHOUSE OPERATIONS */}

                <section className="system-panel settings-card">
                    <div className="system-panel-head">
                        <div>
                            <h2>
                                Warehouse Operations
                            </h2>

                            <p>
                                Jalankan setelah ETL
                                selesai agar warehouse
                                membaca data terbaru.
                            </p>
                        </div>

                        <span className="settings-operation-badge">
                            MANUAL
                        </span>
                    </div>

                    <div className="warehouse-operation">

                        <div className="warehouse-operation-info">
                            <div className="warehouse-icon">
                                DB
                            </div>

                            <div>
                                <strong>
                                    Refresh Warehouse
                                </strong>

                                <span>
                                    Sinkronisasi warehouse
                                    dengan dataset
                                    processed terbaru.
                                </span>
                            </div>
                        </div>

                        <button
                            type="button"
                            className="warehouse-refresh-button"
                            onClick={() =>
                                void handleRefreshWarehouse()
                            }
                            disabled={
                                refreshing ||
                                serviceStatus !==
                                    "online"
                            }
                        >
                            {refreshing
                                ? "Refreshing Warehouse..."
                                : "Refresh Warehouse"}
                        </button>

                        <div className="warehouse-warning">
                            <span>!</span>

                            <span>
                                Jangan jalankan saat ETL
                                masih menulis dataset.
                            </span>
                        </div>

                    </div>
                </section>

                {/* =================================================
                    ANALYTICS STANDARD
                ================================================== */}

                <section className="system-panel settings-card full">
                    <div className="system-panel-head">
                        <div>
                            <h2>
                                Analytics Standard
                            </h2>

                            <p>
                                Standarisasi yang dipakai
                                seluruh dashboard.
                            </p>
                        </div>

                        <span className="settings-operation-badge">
                            STANDARD
                        </span>
                    </div>

                    <div className="analytics-standard-list">

                        <div className="standard-row">
                            <div>
                                <span>
                                    Coordinate System
                                </span>

                                <small>
                                    Sistem koordinat
                                    geografis
                                </small>
                            </div>

                            <strong>
                                WGS84 / EPSG:4326
                            </strong>
                        </div>

                        <div className="standard-row">
                            <div>
                                <span>
                                    Map Area
                                </span>

                                <small>
                                    Wilayah analisis
                                    geografis
                                </small>
                            </div>

                            <strong>
                                UID Lampung
                            </strong>
                        </div>

                        <div className="standard-row">
                            <div>
                                <span>
                                    Pascabayar Repeat
                                </span>

                                <small>
                                    Definisi perulangan
                                    pelanggan
                                </small>
                            </div>

                            <strong>
                                Distinct month
                                occurrence
                            </strong>
                        </div>

                        <div className="standard-row">
                            <div>
                                <span>
                                    Inspection Status
                                </span>

                                <small>
                                    Status pemeriksaan
                                    pelanggan
                                </small>
                            </div>

                            <strong>
                                Latest inspection
                                per IDPEL
                            </strong>
                        </div>

                    </div>
                </section>

            </div>
        </div>
    );
}