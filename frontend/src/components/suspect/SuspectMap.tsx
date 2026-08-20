import {
    useEffect,
    useMemo,
} from "react";

import {
    CircleMarker,
    MapContainer,
    Popup,
    TileLayer,
    useMap,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";

import type {
    SuspectMapPoint,
} from "../../api/suspect";

interface SuspectMapProps {
    points: SuspectMapPoint[];
    height?: number;
}

const DEFAULT_CENTER: [number, number] = [
    -5.3971,
    105.2668,
];

const DEFAULT_ZOOM = 11;
const SINGLE_POINT_ZOOM = 15;
const MAX_ZOOM = 15;

/* ============================================================
 * MAP FITTER
 * ============================================================ */

function MapFitter({
    points,
}: {
    points: SuspectMapPoint[];
}) {
    const map = useMap();

    const bounds = useMemo(() => {
        return points
            .filter(
                (point) =>
                    Number.isFinite(
                        Number(point.latitude),
                    ) &&
                    Number.isFinite(
                        Number(point.longitude),
                    ),
            )
            .map(
                (point) =>
                    [
                        Number(point.latitude),
                        Number(point.longitude),
                    ] as [number, number],
            );
    }, [points]);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            map.invalidateSize();

            if (bounds.length === 0) {
                map.setView(
                    DEFAULT_CENTER,
                    DEFAULT_ZOOM,
                );
                return;
            }

            if (bounds.length === 1) {
                map.setView(
                    bounds[0],
                    SINGLE_POINT_ZOOM,
                );
                return;
            }

            map.fitBounds(bounds, {
                padding: [36, 36],
                maxZoom: MAX_ZOOM,
            });
        }, 50);

        return () => {
            window.clearTimeout(timer);
        };
    }, [map, bounds]);

    return null;
}

/* ============================================================
 * STATUS COLOR
 * ============================================================ */

function getPointColor(
    status?: string | null,
): string {
    const value = String(
        status ?? "",
    )
        .trim()
        .toUpperCase();

    if (
        value === "SUDAH_PERIKSA" ||
        value === "PERIKSA" ||
        value === "SUDAH" ||
        value === "SUDAH DIPERIKSA"
    ) {
        return "#22c55e";
    }

    return "#ef4444";
}

/* ============================================================
 * FORMAT
 * ============================================================ */

function formatNumber(
    value: number | null | undefined,
): string {
    return value == null
        ? "-"
        : Number(value).toLocaleString(
              "id-ID",
          );
}

/* ============================================================
 * GOOGLE MAPS
 * ============================================================ */

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

/* ============================================================
 * COMPONENT
 * ============================================================ */

export default function SuspectMap({
    points,
    height = 560,
}: SuspectMapProps) {
    return (
        <div
            style={{
                width: "100%",
                height,
                overflow: "hidden",
                borderRadius: 12,
                background: "#0f1b2d",
            }}
        >
            <MapContainer
                center={DEFAULT_CENTER}
                zoom={DEFAULT_ZOOM}
                scrollWheelZoom
                preferCanvas
                style={{
                    width: "100%",
                    height: "100%",
                }}
            >
                <TileLayer
                    attribution='&copy; OpenStreetMap contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <MapFitter
                    points={points}
                />

                {points.map((point) => {
                    const latitude = Number(
                        point.latitude,
                    );
                    const longitude = Number(
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

                    const color =
                        getPointColor(
                            point.inspection_status,
                        );

                    const googleMapsUrl =
                        getGoogleMapsUrl(
                            latitude,
                            longitude,
                        );

                    return (
                        <CircleMarker
                            key={`${point.location_code}-${latitude}-${longitude}`}
                            center={[
                                latitude,
                                longitude,
                            ]}
                            radius={5}
                            pathOptions={{
                                color,
                                fillColor: color,
                                fillOpacity: 0.78,
                                weight: 1,
                            }}
                        >
                            <Popup>
                                <div
                                    style={{
                                        minWidth: 245,
                                        fontSize: 13,
                                        lineHeight: 1.55,
                                    }}
                                >
                                    <strong>
                                        {point.location_name ??
                                            "Lokasi Suspect"}
                                    </strong>

                                    <div>
                                        LOCATION_CODE:{" "}
                                        {
                                            point.location_code
                                        }
                                    </div>

                                    {point.idpel && (
                                        <div>
                                            IDPEL:{" "}
                                            {
                                                point.idpel
                                            }
                                        </div>
                                    )}

                                    <div>
                                        Suspect:{" "}
                                        {
                                            point.suspect_name ??
                                            "-"
                                        }
                                    </div>

                                    <div>
                                        UNITAP:{" "}
                                        {
                                            point.unitap ??
                                            "-"
                                        }
                                    </div>

                                    <div>
                                        UNITUP:{" "}
                                        {
                                            point.unitup ??
                                            "-"
                                        }
                                    </div>

                                    <div>
                                        Tarif:{" "}
                                        {
                                            point.tariff ??
                                            "-"
                                        }
                                    </div>

                                    <div>
                                        Daya:{" "}
                                        {formatNumber(
                                            point.power,
                                        )}
                                    </div>

                                    <div>
                                        Status:{" "}
                                        {
                                            point.inspection_status ??
                                            "-"
                                        }
                                    </div>

                                    <div>
                                        Koordinat:{" "}
                                        {latitude.toFixed(
                                            6,
                                        )}
                                        ,{" "}
                                        {longitude.toFixed(
                                            6,
                                        )}
                                    </div>

                                    <a
                                        href={
                                            googleMapsUrl
                                        }
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            display:
                                                "inline-flex",
                                            alignItems:
                                                "center",
                                            justifyContent:
                                                "center",
                                            marginTop: 10,
                                            padding:
                                                "8px 12px",
                                            borderRadius: 7,
                                            background:
                                                "#1d4ed8",
                                            color:
                                                "#ffffff",
                                            textDecoration:
                                                "none",
                                            fontSize: 12,
                                            fontWeight: 700,
                                        }}
                                    >
                                        📍 Buka di Google Maps
                                    </a>
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}
            </MapContainer>
        </div>
    );
}
