import {
    useEffect,
    useMemo,
    useRef,
} from "react";

import {
    MapContainer,
    TileLayer,
    useMap,
} from "react-leaflet";

import L from "leaflet";

import "leaflet/dist/leaflet.css";

import type {
    DlpdMapPoint,
} from "../../api/dlpd";

interface DlpdMapProps {
    points: DlpdMapPoint[];
    height?: number;
}


/* ==========================================================
 * DEFAULT MAP
 * ========================================================== */

const DEFAULT_CENTER: [number, number] = [
    -5.3971,
    105.2668,
];

const DEFAULT_ZOOM = 11;


/* ==========================================================
 * HELPERS
 * ========================================================== */

function formatNumber(
    value: unknown,
): string {
    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "-";
    }

    const numeric = Number(value);

    if (!Number.isFinite(numeric)) {
        return String(value);
    }

    return numeric.toLocaleString("id-ID");
}


function escapeHtml(
    value: unknown,
): string {
    return String(value ?? "-")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* ==========================================================
 * STATUS COLOR
 *
 * ORANGE = belum diperiksa
 * GREEN  = sudah diperiksa
 * ========================================================== */

function getPointColor(
    point: DlpdMapPoint,
): string {
    const status = String(
        point.status ?? "",
    )
        .trim()
        .toUpperCase();

    if (
        status === "BELUM" ||
        status === "BELUM PERIKSA" ||
        status === "BELUM DIPERIKSA"
    ) {
        return "#f59e0b";
    }

    return "#22c55e";
}


/* ==========================================================
 * GOOGLE MAPS URL
 * ========================================================== */

function getGoogleMapsUrl(
    latitude: number,
    longitude: number,
): string {
    return (
        "https://www.google.com/maps/search/?api=1&query=" +
        encodeURIComponent(
            `${latitude},${longitude}`,
        )
    );
}

function getPointGoogleMapsUrl(
    point: DlpdMapPoint,
    latitude: number,
    longitude: number,
    hasCoordinate: boolean,
): string {
    const explicitUrl =
        typeof point.google_maps_url === "string" &&
        point.google_maps_url.trim() !== ""
            ? point.google_maps_url.trim()
            : null;

    if (explicitUrl) {
        return explicitUrl;
    }

    if (hasCoordinate) {
        return getGoogleMapsUrl(
            latitude,
            longitude,
        );
    }

    const idpel = String(
        point.idpel ?? "",
    ).trim();

    return (
        "https://www.google.com/maps/search/?api=1&query=" +
        encodeURIComponent(
            idpel
                ? `IDPEL ${idpel}`
                : "Pelanggan DLPD",
        )
    );
}


/* ==========================================================
 * POPUP CONTENT
 * ========================================================== */

function createPopupContent(
    point: DlpdMapPoint,
): string {
    const latitude = Number(
        point.latitude,
    );

    const longitude = Number(
        point.longitude,
    );

    const hasCoordinate =
        Number.isFinite(latitude) &&
        Number.isFinite(longitude);

    const coordinateText = hasCoordinate
        ? `${latitude.toFixed(10)}, ${longitude.toFixed(10)}`
        : "-";

    const googleMapsUrl =
        getPointGoogleMapsUrl(
            point,
            latitude,
            longitude,
            hasCoordinate,
        );

    const status = String(
        point.status ?? "-",
    );

    const statusUpper = status
        .trim()
        .toUpperCase();

    const statusColor =
        statusUpper === "BELUM" ||
        statusUpper === "BELUM PERIKSA" ||
        statusUpper === "BELUM DIPERIKSA"
            ? "#b45309"
            : "#15803d";

    return `
        <div
            style="
                min-width:260px;
                max-width:340px;
                font-family:Arial, sans-serif;
                font-size:13px;
                line-height:1.55;
                color:#111827;
            "
        >

            <!-- ==========================================
                 TITLE
            =========================================== -->

            <div
                style="
                    font-size:16px;
                    font-weight:700;
                    margin-bottom:10px;
                    color:#111827;
                    border-bottom:1px solid #e5e7eb;
                    padding-bottom:8px;
                "
            >
                ${escapeHtml(
                    point.nama ||
                    point.idpel ||
                    "Pelanggan",
                )}
            </div>


            <!-- ==========================================
                 CUSTOMER INFO
            =========================================== -->

            <div
                style="
                    display:grid;
                    grid-template-columns:90px 1fr;
                    gap:4px 8px;
                "
            >

                <strong>IDPEL</strong>
                <span>
                    ${escapeHtml(point.idpel)}
                </span>

                <strong>UNITUP</strong>
                <span>
                    ${escapeHtml(point.unitup)}
                </span>

                <strong>Tarif</strong>
                <span>
                    ${escapeHtml(point.tariff)}
                </span>

                <strong>Daya</strong>
                <span>
                    ${escapeHtml(
                        formatNumber(point.daya),
                    )}
                    VA
                </span>

                <strong>DLPD</strong>
                <span>
                    ${escapeHtml(point.dlpd)}
                </span>

                <strong>Status</strong>
                <span
                    style="
                        display:inline-block;
                        width:max-content;
                        padding:2px 7px;
                        border-radius:5px;
                        background:${statusColor}18;
                        color:${statusColor};
                        font-weight:600;
                    "
                >
                    ${escapeHtml(status)}
                </span>

                <strong>Koordinat</strong>
                <span>
                    ${escapeHtml(coordinateText)}
                </span>

            </div>


            <!-- ==========================================
                 GOOGLE MAPS
            =========================================== -->

            ${
                googleMapsUrl
                    ? `
                        <div
                            style="
                                margin-top:14px;
                                padding-top:10px;
                                border-top:1px solid #e5e7eb;
                            "
                        >
                            <a
                                href="${escapeHtml(
                                    googleMapsUrl,
                                )}"
                                target="_blank"
                                rel="noopener noreferrer"
                                style="
                                    display:flex;
                                    align-items:center;
                                    justify-content:center;
                                    gap:7px;
                                    width:100%;
                                    box-sizing:border-box;
                                    padding:9px 12px;
                                    border-radius:7px;
                                    background:#2563eb;
                                    color:#ffffff;
                                    text-decoration:none;
                                    font-size:13px;
                                    font-weight:600;
                                "
                            >
                                <span
                                    style="
                                        font-size:14px;
                                    "
                                >
                                    📍
                                </span>

                                ${
                                    hasCoordinate
                                        ? "Buka di Google Maps"
                                        : "Cari IDPEL di Google Maps"
                                }
                            </a>
                        </div>
                    `
                    : ""
            }

        </div>
    `;
}


/* ==========================================================
 * MAP FITTER
 * ========================================================== */

function MapFitter({
    points,
}: {
    points: DlpdMapPoint[];
}) {
    const map = useMap();

    const bounds = useMemo(() => {
        if (points.length === 0) {
            return null;
        }

        let minLat = Infinity;
        let maxLat = -Infinity;

        let minLon = Infinity;
        let maxLon = -Infinity;

        for (const point of points) {
            const lat = Number(
                point.latitude,
            );

            const lon = Number(
                point.longitude,
            );

            if (
                !Number.isFinite(lat) ||
                !Number.isFinite(lon)
            ) {
                continue;
            }

            minLat = Math.min(
                minLat,
                lat,
            );

            maxLat = Math.max(
                maxLat,
                lat,
            );

            minLon = Math.min(
                minLon,
                lon,
            );

            maxLon = Math.max(
                maxLon,
                lon,
            );
        }

        if (
            !Number.isFinite(minLat) ||
            !Number.isFinite(maxLat) ||
            !Number.isFinite(minLon) ||
            !Number.isFinite(maxLon)
        ) {
            return null;
        }

        return L.latLngBounds(
            [minLat, minLon],
            [maxLat, maxLon],
        );
    }, [points]);


    useEffect(() => {
        if (!bounds) {
            map.setView(
                DEFAULT_CENTER,
                DEFAULT_ZOOM,
            );

            return;
        }

        const southWest =
            bounds.getSouthWest();

        const northEast =
            bounds.getNorthEast();

        /*
         * Satu titik.
         */
        if (
            southWest.equals(
                northEast,
            )
        ) {
            map.setView(
                bounds.getCenter(),
                15,
            );

            return;
        }

        /*
         * Banyak titik.
         */
        map.fitBounds(
            bounds,
            {
                padding: [
                    40,
                    40,
                ],
                maxZoom: 15,
            },
        );
    }, [
        map,
        bounds,
    ]);

    return null;
}


/* ==========================================================
 * CANVAS POINT LAYER
 *
 * Jangan render ribuan CircleMarker React.
 *
 * Semua titik digambar pada SATU canvas.
 * Ini jauh lebih ringan untuk dataset besar.
 * ========================================================== */

function CanvasPointLayer({
    points,
}: {
    points: DlpdMapPoint[];
}) {
    const map = useMap();

    const canvasRef =
        useRef<HTMLCanvasElement | null>(
            null,
        );

    const containerRef =
        useRef<HTMLElement | null>(
            null,
        );


    /* ======================================================
     * PREPARE POINTS
     * ====================================================== */

    const preparedPoints =
        useMemo(() => {
            return points
                .map((point) => {
                    const latitude =
                        Number(
                            point.latitude,
                        );

                    const longitude =
                        Number(
                            point.longitude,
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
                        point,
                        latitude,
                        longitude,
                        color:
                            getPointColor(
                                point,
                            ),
                    };
                })
                .filter(
                    (
                        item,
                    ): item is {
                        point: DlpdMapPoint;
                        latitude: number;
                        longitude: number;
                        color: string;
                    } =>
                        item !== null,
                );
        }, [points]);


    /* ======================================================
     * CREATE CANVAS
     * ====================================================== */

    useEffect(() => {
        const container =
            map.getContainer();

        if (!container) {
            return;
        }

        /*
         * Render canvas LANGSUNG di map container.
         *
         * Jangan append ke overlayPane. Leaflet memposisikan pane dengan
         * transform sendiri, sedangkan latLngToLayerPoint() menghasilkan
         * koordinat relatif terhadap map container. Jika canvas ditempel
         * ke overlayPane, koordinat titik dapat bergeser/keluar viewport
         * sehingga base map tampil tetapi titik tidak terlihat.
         */
        const canvas =
            document.createElement(
                "canvas",
            );

        canvas.style.position =
            "absolute";

        canvas.style.left = "0";
        canvas.style.top = "0";

        canvas.style.width =
            "100%";

        canvas.style.height =
            "100%";

        canvas.style.pointerEvents =
            "none";

        canvas.style.zIndex =
            "450";

        container.appendChild(
            canvas,
        );

        canvasRef.current =
            canvas;

        containerRef.current =
            container;

        return () => {
            canvas.remove();

            canvasRef.current =
                null;

            containerRef.current =
                null;
        };
    }, [map]);


    /* ======================================================
     * DRAW
     * ====================================================== */

    useEffect(() => {
        const canvas =
            canvasRef.current;

        const container =
            containerRef.current;

        if (
            !canvas ||
            !container
        ) {
            return;
        }

        let animationFrame = 0;


        const draw = () => {
            animationFrame = 0;

            const width =
                container.clientWidth;

            const height =
                container.clientHeight;

            if (
                width <= 0 ||
                height <= 0
            ) {
                return;
            }

            const devicePixelRatio =
                Math.min(
                    window.devicePixelRatio ||
                        1,
                    2,
                );

            const canvasWidth =
                Math.round(
                    width *
                        devicePixelRatio,
                );

            const canvasHeight =
                Math.round(
                    height *
                        devicePixelRatio,
                );

            if (
                canvas.width !==
                    canvasWidth ||
                canvas.height !==
                    canvasHeight
            ) {
                canvas.width =
                    canvasWidth;

                canvas.height =
                    canvasHeight;
            }

            const context =
                canvas.getContext(
                    "2d",
                );

            if (!context) {
                return;
            }

            context.clearRect(
                0,
                0,
                canvas.width,
                canvas.height,
            );

            context.save();

            context.scale(
                devicePixelRatio,
                devicePixelRatio,
            );

            const zoom =
                map.getZoom();


            /*
             * Marker size.
             */

            let radius = 2;

            if (zoom >= 10) {
                radius = 2.5;
            }

            if (zoom >= 12) {
                radius = 3;
            }

            if (zoom >= 14) {
                radius = 4;
            }


            /*
             * Semua titik tetap dipertahankan.
             *
             * Hanya titik di luar viewport
             * yang tidak digambar.
             */

            for (
                let index = 0;
                index <
                preparedPoints.length;
                index += 1
            ) {
                const item =
                    preparedPoints[
                        index
                    ];

                const layerPoint =
                    map.latLngToLayerPoint(
                        L.latLng(
                            item.latitude,
                            item.longitude,
                        ),
                    );

                const x =
                    layerPoint.x;

                const y =
                    layerPoint.y;


                /*
                 * Skip titik yang jauh di luar
                 * layar untuk menghemat rendering.
                 */

                if (
                    x < -radius ||
                    x >
                        width +
                            radius ||
                    y < -radius ||
                    y >
                        height +
                            radius
                ) {
                    continue;
                }


                context.beginPath();

                context.arc(
                    x,
                    y,
                    radius,
                    0,
                    Math.PI * 2,
                );

                context.fillStyle =
                    item.color;

                context.globalAlpha =
                    zoom <= 9
                        ? 0.45
                        : 0.72;

                context.fill();


                /*
                 * Border ketika zoom dekat.
                 */

                if (zoom >= 12) {
                    context.strokeStyle =
                        item.color;

                    context.globalAlpha =
                        0.95;

                    context.lineWidth =
                        0.7;

                    context.stroke();
                }
            }

            context.restore();
        };


        const requestDraw =
            () => {
                if (
                    animationFrame !==
                    0
                ) {
                    return;
                }

                animationFrame =
                    window.requestAnimationFrame(
                        draw,
                    );
            };


        requestDraw();

        /*
         * MapFitter dapat mengubah view tepat setelah effect ini dipasang.
         * Gambar ulang setelah Leaflet selesai melakukan perubahan view.
         */
        map.once(
            "moveend",
            requestDraw,
        );


        /*
         * Map movement.
         */

        map.on(
            "move",
            requestDraw,
        );

        map.on(
            "zoom",
            requestDraw,
        );

        map.on(
            "resize",
            requestDraw,
        );

        map.on(
            "moveend",
            requestDraw,
        );

        map.on(
            "zoomend",
            requestDraw,
        );


        /*
         * Container resize.
         */

        const resizeObserver =
            new ResizeObserver(
                requestDraw,
            );

        resizeObserver.observe(
            container,
        );


        return () => {
            map.off(
                "move",
                requestDraw,
            );

            map.off(
                "zoom",
                requestDraw,
            );

            map.off(
                "resize",
                requestDraw,
            );

            map.off(
                "moveend",
                requestDraw,
            );

            map.off(
                "zoomend",
                requestDraw,
            );

            resizeObserver.disconnect();

            if (
                animationFrame !==
                0
            ) {
                window.cancelAnimationFrame(
                    animationFrame,
                );
            }
        };
    }, [
        map,
        preparedPoints,
    ]);


    /* ======================================================
     * CLICK → FIND NEAREST POINT → POPUP
     * ====================================================== */

    useEffect(() => {
        if (
            preparedPoints.length === 0
        ) {
            return;
        }

        const handleMapClick =
            (
                event: L.LeafletMouseEvent,
            ) => {
                const clickPoint =
                    map.latLngToLayerPoint(
                        event.latlng,
                    );

                const zoom =
                    map.getZoom();

                const hitRadius =
                    zoom >= 14
                        ? 14
                        : 10;

                const hitRadiusSquared =
                    hitRadius *
                    hitRadius;

                const visibleBounds =
                    map.getBounds().pad(0.02);

                let nearest:
                    | {
                          item: (
                              typeof preparedPoints
                          )[number];
                          distanceSquared: number;
                      }
                    | null =
                    null;

                // Hanya periksa titik yang berada di viewport.
                // Data asli tetap utuh; ini hanya memperkecil pekerjaan
                // saat user melakukan click.
                for (
                    let index = 0;
                    index <
                    preparedPoints.length;
                    index += 1
                ) {
                    const item =
                        preparedPoints[
                            index
                        ];

                    const layerPoint =
                        map.latLngToLayerPoint(
                            L.latLng(
                                item.latitude,
                                item.longitude,
                            ),
                        );

                    if (
                        !visibleBounds.contains(
                            L.latLng(
                                item.latitude,
                                item.longitude,
                            ),
                        )
                    ) {
                        continue;
                    }

                    const dx =
                        layerPoint.x -
                        clickPoint.x;

                    const dy =
                        layerPoint.y -
                        clickPoint.y;

                    const distanceSquared =
                        dx * dx +
                        dy * dy;

                    if (
                        distanceSquared >
                        hitRadiusSquared
                    ) {
                        continue;
                    }

                    if (
                        nearest === null ||
                        distanceSquared <
                            nearest.distanceSquared
                    ) {
                        nearest = {
                            item,
                            distanceSquared,
                        };
                    }
                }

                if (
                    nearest === null
                ) {
                    return;
                }

                const point =
                    nearest.item.point;

                L.popup({
                    maxWidth: 360,
                    closeButton: true,
                })
                    .setLatLng(
                        event.latlng,
                    )
                    .setContent(
                        createPopupContent(
                            point,
                        ),
                    )
                    .openOn(map);
            };


        map.on(
            "click",
            handleMapClick,
        );

        return () => {
            map.off(
                "click",
                handleMapClick,
            );
        };
    }, [
        map,
        preparedPoints,
    ]);


    return null;
}


/* ==========================================================
 * MAIN COMPONENT
 * ========================================================== */

export default function DlpdMap({
    points,
    height = 520,
}: DlpdMapProps) {

    /*
     * Validasi koordinat.
     *
     * Area dibatasi pada wilayah Lampung.
     *
     * Tidak ada sampling.
     * Tidak ada limit 2.500.
     */

    const validPoints =
        useMemo(
            () =>
                points.filter(
                    (point) => {
                        const lat =
                            Number(
                                point.latitude,
                            );

                        const lon =
                            Number(
                                point.longitude,
                            );

                        return (
                            Number.isFinite(
                                lat,
                            ) &&
                            Number.isFinite(
                                lon,
                            ) &&
                            lat >= -6.6 &&
                            lat <= -3.7 &&
                            lon >= 103.0 &&
                            lon <= 106.5
                        );
                    },
                ),
            [points],
        );


    return (
        <div
            style={{
                width: "100%",
                height,
                minHeight: 300,
                borderRadius: 10,
                overflow: "hidden",
                position: "relative",
                background:
                    "#0f1b2d",
            }}
        >
            <MapContainer
                center={
                    DEFAULT_CENTER
                }
                zoom={
                    DEFAULT_ZOOM
                }
                scrollWheelZoom
                preferCanvas
                style={{
                    width: "100%",
                    height: "100%",
                }}
            >

                {/* ==========================================
                    BASE MAP
                =========================================== */}

                <TileLayer
                    attribution='&copy; OpenStreetMap contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />


                {/* ==========================================
                    AUTO FIT
                =========================================== */}

                <MapFitter
                    points={
                        validPoints
                    }
                />


                {/* ==========================================
                    POINTS
                =========================================== */}

                <CanvasPointLayer
                    points={
                        validPoints
                    }
                />

                <div
                    style={{
                        position: "absolute",
                        right: 12,
                        bottom: 12,
                        zIndex: 500,
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "7px 10px",
                        borderRadius: 8,
                        background: "rgba(15, 23, 42, 0.92)",
                        color: "#e2e8f0",
                        fontSize: 11,
                        boxShadow:
                            "0 4px 14px rgba(0,0,0,0.18)",
                        pointerEvents: "none",
                    }}
                >
                    <span
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 5,
                        }}
                    >
                        <span
                            style={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                background: "#22c55e",
                            }}
                        />
                        Sudah Periksa
                    </span>

                    <span
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 5,
                        }}
                    >
                        <span
                            style={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                background: "#f59e0b",
                            }}
                        />
                        Belum Periksa
                    </span>
                </div>

            </MapContainer>
        </div>
    );
}