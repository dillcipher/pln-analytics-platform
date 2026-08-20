import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import {
    getExecutiveCharts,
    getExecutiveKpis,
    getExecutiveMonths,
    type ExecutiveCharts,
    type ExecutiveKpi,
    type ExecutiveMonth,
} from "../api/executive";

// ==========================================================
// HELPERS
// ==========================================================

function n(value: number | null | undefined): number {
    const result = Number(value);
    return Number.isFinite(result) ? result : 0;
}

function formatNumber(value: number | null | undefined): string {
    return n(value).toLocaleString("id-ID");
}

function formatPercent(value: number | null | undefined): string {
    return `${n(value).toFixed(1)}%`;
}

function formatPValue(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(Number(value))) return "N/A";
    const p = Number(value);
    if (p < 0.001) return "< 0.001";
    return p.toFixed(4);
}

function monthLabel(months: ExecutiveMonth[], key: string): string {
    return months.find((item) => item.month_key === key)?.label ?? key ?? "-";
}

function truncate(value: string, max = 24): string {
    return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

// ==========================================================
// DATA SCIENCE CONTRACT
// ==========================================================

interface ExecutiveDataScience {
    correlation: Array<{
        feature_x: string;
        feature_y: string;
        correlation: number;
        abs_correlation: number;
        p_value?: number | null;
        sample_size?: number | null;
        significant?: boolean | null;
    }>;
    linear_regression: Array<{
        feature: string;
        target: string;
        slope: number;
        intercept: number;
        r_squared: number;
        sample_size: number;
        p_value?: number | null;
        significant?: boolean | null;
    }>;
    feature_importance: Array<{
        feature: string;
        target: string;
        importance: number;
        direction?: string | null;
        correlation?: number | null;
    }>;
    pra_pasca_classification: Array<{
        customer_type: string;
        classification: string;
        total: number;
    }>;

    priority_by_classification: Array<{
        classification: string;
        pra_total: number;
        pasca_total: number;
        repeat_locations: number;
        repeat_occurrences: number;
        priority_score: number;
    }>;

    priority_by_unitap: Array<{
        unitap: string;
        pra_locations: number;
        pasca_locations: number;
        repeat_locations: number;
        repeat_occurrences: number;
        repeat_rate_pct: number;
        priority_score: number;
    }>;

    inspection_coverage: {
        total_population: number;
        inspected: number;
        remaining: number;
        normal: number;
        findings: number;
        coverage_pct: number;
        finding_rate_pct: number;
    };

    repeat_intensity: {
        total_locations: number;
        repeat_locations: number;
        repeat_occurrences: number;
        repeat_rate_pct: number;
        avg_repeat_occurrences_per_repeat_location: number;
        max_repeat_count: number;
    };

    concentration: {
        unitap: Array<{
            unitap: string;
            locations: number;
            share_pct: number;
        }>;
        top_unitap: {
            unitap: string;
            locations: number;
            share_pct: number;
        } | null;
        top_3_share_pct: number;
    };
}

type ExecutiveChartsWithDataScience = ExecutiveCharts & {
    data_science: ExecutiveDataScience;
};

function emptyDataScience(): ExecutiveDataScience {
    return {
        correlation: [],
        linear_regression: [],
        feature_importance: [],
        pra_pasca_classification: [],
        priority_by_classification: [],
        priority_by_unitap: [],
        inspection_coverage: {
            total_population: 0,
            inspected: 0,
            remaining: 0,
            normal: 0,
            findings: 0,
            coverage_pct: 0,
            finding_rate_pct: 0,
        },
        repeat_intensity: {
            total_locations: 0,
            repeat_locations: 0,
            repeat_occurrences: 0,
            repeat_rate_pct: 0,
            avg_repeat_occurrences_per_repeat_location: 0,
            max_repeat_count: 0,
        },
        concentration: {
            unitap: [],
            top_unitap: null,
            top_3_share_pct: 0,
        },
    };
}

function emptyCharts(): ExecutiveChartsWithDataScience {
    return {
        bar_by_unitap: [],
        pie_by_tariff: [],
        donut_by_segment: [],
        monthly_trend: [],
        ranking_by_ulp: [],
        heatmap_unitap_x_category: [],
        anev_classification: [],
        anev_by_unitap: [],
        anev_by_tariff: [],
        pra_monthly: {
            total_locations: 0,
            total_classifications: 0,
            classification: [],
            unitap: [],
        },
        pasca_repeat: {
            total_locations: 0,
            repeat_locations: 0,
            repeat_occurrences: 0,
            repeat_rate_pct: 0,
            frequency: [],
            classification: [],
        },
        repeat_cases: [],
        data_science: emptyDataScience(),
    };
}

// ==========================================================
// THEME / LAYOUT
// ==========================================================

const C = {
    page: "#07111f",
    card: "#0f1a2a",
    cardAlt: "#111f31",
    border: "#223149",
    text: "#f8fafc",
    muted: "#8fa3bd",
    grid: "#26364c",
    accent: "#6f8fe8",
    good: "#52c7a5",
    warning: "#eab66a",
    danger: "#e56b7a",
};

const pageStyle: React.CSSProperties = {
    width: "100%",
    minHeight: "100%",
    boxSizing: "border-box",
    padding: "24px 32px 52px",
    color: C.text,
    background: C.page,
};

const cardStyle: React.CSSProperties = {
    background: C.card,
    border: `1px solid ${C.border}`,
    borderRadius: 14,
    boxSizing: "border-box",
};

const chartCardStyle: React.CSSProperties = {
    ...cardStyle,
    padding: 18,
    minWidth: 0,
    overflow: "hidden",
};

const sectionStyle: React.CSSProperties = { marginBottom: 32 };

const sectionTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: 20,
    lineHeight: 1.2,
    fontWeight: 800,
};

const sectionDescriptionStyle: React.CSSProperties = {
    margin: "7px 0 16px",
    color: C.muted,
    fontSize: 13,
    lineHeight: 1.55,
};

const gridTwo: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(390px, 1fr))",
    gap: 16,
};

const gridFour: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 12,
};

function KpiCard({
    title,
    value,
    description,
    tone = "normal",
}: {
    title: string;
    value: string;
    description: string;
    tone?: "normal" | "good" | "warning" | "danger";
}) {
    const accent =
        tone === "good"
            ? C.good
            : tone === "warning"
              ? C.warning
              : tone === "danger"
                ? C.danger
                : C.accent;

    return (
        <div style={{ ...cardStyle, padding: "16px 17px", minHeight: 116 }}>
            <div style={{ color: C.muted, fontSize: 12, marginBottom: 7 }}>
                {title}
            </div>
            <div
                style={{
                    color: C.text,
                    fontSize: 25,
                    lineHeight: 1.15,
                    fontWeight: 800,
                    overflowWrap: "anywhere",
                }}
            >
                {value}
            </div>
            <div
                style={{
                    marginTop: 7,
                    color: accent,
                    fontSize: 11,
                    lineHeight: 1.4,
                }}
            >
                {description}
            </div>
        </div>
    );
}

function MiniMetric({
    label,
    value,
    description,
}: {
    label: string;
    value: string;
    description: string;
}) {
    return (
        <div
            style={{
                padding: 14,
                borderRadius: 10,
                background: C.cardAlt,
                border: `1px solid ${C.border}`,
            }}
        >
            <div style={{ color: C.muted, fontSize: 11 }}>{label}</div>
            <div style={{ marginTop: 4, fontSize: 22, fontWeight: 800 }}>{value}</div>
            <div style={{ marginTop: 3, color: C.muted, fontSize: 11, lineHeight: 1.4 }}>
                {description}
            </div>
        </div>
    );
}

// ==========================================================
// ECHART BASE
// ==========================================================

const axisLabel = { color: C.muted, fontSize: 10 };

function baseOption() {
    return {
        textStyle: { color: C.text },
        animationDuration: 250,
        tooltip: {
            backgroundColor: "#132238",
            borderColor: C.border,
            textStyle: { color: C.text, fontSize: 12 },
        },
    };
}

function emptyOption(message = "Belum ada data") {
    return {
        ...baseOption(),
        graphic: {
            type: "text",
            left: "center",
            top: "middle",
            style: { text: message, fill: C.muted, fontSize: 13 },
        },
    };
}

function horizontalBar(
    data: { label: string; value: number }[],
    color = C.accent,
    limit = 10,
) {
    if (!data.length) return emptyOption();

    const sorted = [...data]
        .sort((a, b) => n(b.value) - n(a.value))
        .slice(0, limit);

    return {
        ...baseOption(),
        grid: { left: 12, right: 60, top: 12, bottom: 12, containLabel: true },
        xAxis: {
            type: "value",
            min: 0,
            axisLabel,
            splitLine: { lineStyle: { color: C.grid } },
            axisLine: { lineStyle: { color: C.grid } },
        },
        yAxis: {
            type: "category",
            inverse: true,
            data: sorted.map((x) => truncate(x.label, 30)),
            axisLabel: { ...axisLabel, width: 190, overflow: "truncate" },
            axisTick: { show: false },
        },
        tooltip: {
            ...baseOption().tooltip,
            trigger: "axis",
            axisPointer: { type: "shadow" },
            formatter: (params: any) => {
                const item = sorted[Number(params?.[0]?.dataIndex ?? 0)];
                return item
                    ? `${item.label}<br/><b>${formatNumber(item.value)}</b> lokasi`
                    : "-";
            },
        },
        series: [{
            type: "bar",
            data: sorted.map((x) => n(x.value)),
            barMaxWidth: 25,
            itemStyle: { color, borderRadius: [0, 5, 5, 0] },
            label: {
                show: true,
                position: "right",
                color: C.text,
                fontSize: 10,
                formatter: (p: any) => formatNumber(p.value),
            },
        }],
    };
}

function heatmapOption(raw: ExecutiveCharts["heatmap_unitap_x_category"]) {
    if (!raw.length) return emptyOption();

    const unitaps = Array.from(new Set(raw.map((x) => x.unitap)));
    const categories = Array.from(new Set(raw.map((x) => x.category)));
    const values = raw.map((x) => [
        unitaps.indexOf(x.unitap),
        categories.indexOf(x.category),
        n(x.value),
    ]);
    const max = Math.max(...values.map((x) => n(x[2])), 1);

    return {
        ...baseOption(),
        grid: { left: 120, right: 20, top: 18, bottom: 70, containLabel: true },
        xAxis: {
            type: "category",
            data: unitaps,
            axisLabel: { ...axisLabel, rotate: 35 },
        },
        yAxis: {
            type: "category",
            data: categories,
            axisLabel: { ...axisLabel, width: 150, overflow: "truncate" },
        },
        visualMap: {
            min: 0,
            max,
            calculable: true,
            orient: "horizontal",
            left: "center",
            bottom: 5,
            textStyle: { color: C.muted, fontSize: 10 },
        },
        tooltip: {
            ...baseOption().tooltip,
            formatter: (p: any) => {
                const v = p?.value ?? [];
                return `${unitaps[v[0]] ?? "-"}<br/>${categories[v[1]] ?? "-"}<br/><b>${formatNumber(v[2])}</b> lokasi`;
            },
        },
        series: [{
            type: "heatmap",
            data: values,
            label: {
                show: true,
                color: C.text,
                fontSize: 9,
                formatter: (p: any) => formatNumber(p.value?.[2]),
            },
            itemStyle: { borderColor: C.card, borderWidth: 1 },
        }],
    };
}

function praPasca100Option(data: ExecutiveDataScience["pra_pasca_classification"]) {
    if (!data.length) return emptyOption();

    const classifications = Array.from(new Set(data.map((x) => x.classification)));
    const pra = classifications.map((classification) =>
        n(data.find((x) => x.classification === classification && x.customer_type.toUpperCase() === "PRA")?.total),
    );
    const pasca = classifications.map((classification) =>
        n(data.find((x) => x.classification === classification && x.customer_type.toUpperCase() === "PASCA")?.total),
    );

    return {
        ...baseOption(),
        grid: { left: 42, right: 20, top: 42, bottom: 100, containLabel: true },
        legend: { top: 0, textStyle: { color: C.muted, fontSize: 11 } },
        xAxis: {
            type: "category",
            data: classifications.map((x) => truncate(x, 18)),
            axisLabel: { ...axisLabel, rotate: 35 },
        },
        yAxis: {
            type: "value",
            min: 0,
            max: 100,
            axisLabel: { ...axisLabel, formatter: "{value}%" },
            splitLine: { lineStyle: { color: C.grid } },
        },
        tooltip: {
            ...baseOption().tooltip,
            trigger: "axis",
            axisPointer: { type: "shadow" },
            formatter: (params: any) => {
                const index = Number(params?.[0]?.dataIndex ?? 0);
                const p = pra[index] ?? 0;
                const s = pasca[index] ?? 0;
                const total = p + s;
                if (!total) return classifications[index] ?? "-";
                return [
                    classifications[index] ?? "-",
                    `PRA: <b>${formatNumber(p)}</b> (${(p / total * 100).toFixed(1)}%)`,
                    `PASCA: <b>${formatNumber(s)}</b> (${(s / total * 100).toFixed(1)}%)`,
                ].join("<br/>");
            },
        },
        series: [
            {
                name: "PRA",
                type: "bar",
                stack: "share",
                data: pra.map((value, index) => {
                    const total = value + pasca[index];
                    return total ? value / total * 100 : 0;
                }),
                itemStyle: { color: C.accent },
            },
            {
                name: "PASCA",
                type: "bar",
                stack: "share",
                data: pasca.map((value, index) => {
                    const total = value + pra[index];
                    return total ? value / total * 100 : 0;
                }),
                itemStyle: { color: C.warning },
            },
        ],
    };
}

function monthlyTrendOption(data: ExecutiveCharts["monthly_trend"]) {
    if (!data.length) return emptyOption();

    return {
        ...baseOption(),
        grid: { left: 42, right: 18, top: 22, bottom: 42, containLabel: true },
        xAxis: {
            type: "category",
            data: data.map((x) => x.label),
            axisLabel,
            axisLine: { lineStyle: { color: C.grid } },
        },
        yAxis: {
            type: "value",
            min: 0,
            axisLabel,
            splitLine: { lineStyle: { color: C.grid } },
        },
        tooltip: { ...baseOption().tooltip, trigger: "axis" },
        series: [{
            type: "line",
            smooth: true,
            data: data.map((x) => n(x.value)),
            symbol: "circle",
            symbolSize: 6,
            lineStyle: { color: C.accent, width: 3 },
            itemStyle: { color: C.accent },
            areaStyle: { color: "rgba(111,143,232,0.10)" },
        }],
    };
}

// ==========================================================
// DATA SCIENCE VISUALS
// ==========================================================

function dataScienceCorrelationOption(
    data: ExecutiveDataScience["correlation"],
) {
    if (!data.length) return emptyOption("Belum ada data correlation");

    const sorted = [...data]
        .sort((a, b) => n(b.abs_correlation) - n(a.abs_correlation))
        .slice(0, 12);

    return {
        ...baseOption(),
        grid: { left: 145, right: 44, top: 18, bottom: 28, containLabel: true },
        xAxis: {
            type: "value",
            min: -1,
            max: 1,
            axisLabel: { ...axisLabel, formatter: (v: number) => Number(v).toFixed(1) },
            splitLine: { lineStyle: { color: C.grid } },
            axisLine: { lineStyle: { color: C.grid } },
        },
        yAxis: {
            type: "category",
            inverse: true,
            data: sorted.map(
                (x) => `${truncate(x.feature_x, 18)} × ${truncate(x.feature_y, 18)}`,
            ),
            axisLabel: { ...axisLabel, width: 135, overflow: "truncate" },
            axisTick: { show: false },
        },
        tooltip: {
            ...baseOption().tooltip,
            trigger: "axis",
            axisPointer: { type: "shadow" },
            formatter: (params: any) => {
                const item = sorted[Number(params?.[0]?.dataIndex ?? 0)];
                if (!item) return "-";
                return [
                    `<b>${item.feature_x}</b> × ${item.feature_y}`,
                    `r = <b>${n(item.correlation).toFixed(4)}</b>`,
                    `|r| = ${n(item.abs_correlation).toFixed(4)}`,
                    `p-value = <b>${formatPValue(item.p_value)}</b>`,
                    `N = ${formatNumber(item.sample_size)}`,
                    item.significant == null
                        ? ""
                        : item.significant
                          ? `<span style="color:${C.good}">Signifikan (α = 0,05)</span>`
                          : `<span style="color:${C.warning}">Tidak signifikan (α = 0,05)</span>`,
                ]
                    .filter(Boolean)
                    .join("<br/>");
            },
        },
        series: [
            {
                type: "bar",
                data: sorted.map((x) => n(x.correlation)),
                barMaxWidth: 22,
                itemStyle: {
                    color: (p: any) =>
                        n(p.value) < 0 ? C.warning : C.accent,
                    borderRadius: [0, 5, 5, 0],
                },
                label: {
                    show: true,
                    position: "right",
                    color: C.text,
                    fontSize: 9,
                    formatter: (p: any) => n(p.value).toFixed(3),
                },
            },
        ],
    };
}

function dataScienceRegressionOption(
    data: ExecutiveDataScience["linear_regression"],
) {
    if (!data.length) return emptyOption("Belum ada model regression");

    const sorted = [...data]
        .sort((a, b) => n(b.r_squared) - n(a.r_squared))
        .slice(0, 10);

    return {
        ...baseOption(),
        grid: { left: 135, right: 40, top: 18, bottom: 42, containLabel: true },
        xAxis: {
            type: "category",
            data: sorted.map((x) => truncate(x.feature, 18)),
            axisLabel,
            axisTick: { show: false },
        },
        yAxis: {
            type: "value",
            min: 0,
            max: 1,
            axisLabel: { ...axisLabel, formatter: (v: number) => Number(v).toFixed(1) },
            splitLine: { lineStyle: { color: C.grid } },
        },
        tooltip: {
            ...baseOption().tooltip,
            trigger: "axis",
            axisPointer: { type: "shadow" },
            formatter: (params: any) => {
                const item = sorted[Number(params?.[0]?.dataIndex ?? 0)];
                if (!item) return "-";
                return [
                    `<b>${item.feature}</b> → ${item.target}`,
                    `R² = <b>${n(item.r_squared).toFixed(4)}</b>`,
                    `slope = ${n(item.slope).toFixed(6)}`,
                    `p-value = <b>${formatPValue(item.p_value)}</b>`,
                    `N = ${formatNumber(item.sample_size)}`,
                    item.significant == null
                        ? ""
                        : item.significant
                          ? `<span style="color:${C.good}">Model signifikan</span>`
                          : `<span style="color:${C.warning}">Model tidak signifikan</span>`,
                ]
                    .filter(Boolean)
                    .join("<br/>");
            },
        },
        series: [
            {
                type: "bar",
                data: sorted.map((x) => n(x.r_squared)),
                barMaxWidth: 34,
                itemStyle: {
                    color: C.good,
                    borderRadius: [5, 5, 0, 0],
                },
                label: {
                    show: true,
                    position: "top",
                    color: C.text,
                    fontSize: 9,
                    formatter: (p: any) => n(p.value).toFixed(3),
                },
            },
        ],
    };
}

function dataScienceFeatureImportanceOption(
    data: ExecutiveDataScience["feature_importance"],
) {
    if (!data.length) return emptyOption("Belum ada feature importance");

    const sorted = [...data]
        .sort((a, b) => n(b.importance) - n(a.importance))
        .slice(0, 12);

    return horizontalBar(
        sorted.map((x) => ({
            label: x.feature,
            value: n(x.importance),
        })),
        C.good,
        12,
    );
}

function significanceTone(
    p: number | null | undefined,
    significant?: boolean | null,
) {
    if (significant === true || (p != null && Number(p) <= 0.05)) {
        return "good" as const;
    }
    if (significant === false || p != null) {
        return "warning" as const;
    }
    return "normal" as const;
}

// ==========================================================
// PAGE
// ==========================================================

export default function ExecutivePage() {
    const [months, setMonths] = useState<ExecutiveMonth[]>([]);
    const [selectedMonth, setSelectedMonth] = useState("");
    const [kpi, setKpi] = useState<ExecutiveKpi | null>(null);
    const [charts, setCharts] = useState<ExecutiveChartsWithDataScience>(emptyCharts());
    const [loadingMonths, setLoadingMonths] = useState(true);
    const [loadingData, setLoadingData] = useState(false);
    const [error, setError] = useState("");

    // ------------------------------------------------------
    // MONTHS
    // ------------------------------------------------------

    useEffect(() => {
        let cancelled = false;

        async function loadMonths() {
            setLoadingMonths(true);

            try {
                const data = await getExecutiveMonths();

                if (cancelled) return;

                const unique = Array.from(
                    new Map(
                        data
                            .filter((item) => item.month_key)
                            .map((item) => [item.month_key, item]),
                    ).values(),
                ).sort((a, b) => a.month_key.localeCompare(b.month_key));

                setMonths(unique);

                if (unique.length) {
                    setSelectedMonth((current) =>
                        unique.some((item) => item.month_key === current)
                            ? current
                            : unique[unique.length - 1].month_key,
                    );
                } else {
                    setError("Endpoint bulan tidak mengembalikan periode yang tersedia.");
                }
            } catch (err) {
                console.error("Failed to load executive months:", err);
                if (!cancelled) {
                    setError("Gagal memuat daftar bulan Executive Dashboard.");
                }
            } finally {
                if (!cancelled) setLoadingMonths(false);
            }
        }

        void loadMonths();

        return () => {
            cancelled = true;
        };
    }, []);

    // ------------------------------------------------------
    // SELECTED MONTH
    // ------------------------------------------------------

    useEffect(() => {
        if (!selectedMonth) return;

        let cancelled = false;

        async function loadExecutive() {
            setLoadingData(true);
            setError("");

            try {
                const [kpiData, chartData] = await Promise.all([
                    getExecutiveKpis(selectedMonth),
                    getExecutiveCharts(selectedMonth),
                ]);

                if (cancelled) return;

                setKpi(kpiData);
                setCharts(chartData as ExecutiveChartsWithDataScience);
            } catch (err) {
                console.error("Failed to load Executive Dashboard:", err);

                if (!cancelled) {
                    setError(
                        `Gagal memuat data periode ${selectedMonth}. Pastikan API menerima month=${selectedMonth}.`,
                    );
                }
            } finally {
                if (!cancelled) setLoadingData(false);
            }
        }

        void loadExecutive();

        return () => {
            cancelled = true;
        };
    }, [selectedMonth]);

    const pasca = charts.pasca_repeat;
    const ds = charts.data_science ?? emptyDataScience();

    // ------------------------------------------------------
    // DECISION METRICS
    // ------------------------------------------------------

    const insight = useMemo(() => {
        const classifications = [...(charts.anev_classification ?? [])]
            .map((x) => ({ label: x.label, value: n(x.value) }))
            .sort((a, b) => b.value - a.value);

        const ulps = [...(charts.ranking_by_ulp ?? [])]
            .map((x) => ({ label: x.label, value: n(x.value) }))
            .sort((a, b) => b.value - a.value);

        const heatmap = [...(charts.heatmap_unitap_x_category ?? [])]
            .map((x) => ({
                unitap: x.unitap,
                category: x.category,
                value: n(x.value),
            }))
            .sort((a, b) => b.value - a.value);

        const totalClassification = classifications.reduce(
            (sum, item) => sum + item.value,
            0,
        );

        const top3 = classifications
            .slice(0, 3)
            .reduce((sum, item) => sum + item.value, 0);

        const topUlp = ulps[0] ?? null;
        const topClass = classifications[0] ?? null;
        const topHeatmap = heatmap[0] ?? null;

        const suspect = n(kpi?.total_suspects);
        const findings = n(kpi?.total_findings);

        const findingRate = suspect > 0
            ? findings / suspect * 100
            : 0;

        const trend = [...(charts.monthly_trend ?? [])]
            .map((x) => ({ label: x.label, value: n(x.value) }))
            .sort((a, b) => a.label.localeCompare(b.label));

        const latestTrend = trend[trend.length - 1] ?? null;
        const previousTrend = trend[trend.length - 2] ?? null;

        const trendDeltaPct =
            previousTrend && previousTrend.value > 0 && latestTrend
                ? (latestTrend.value - previousTrend.value) /
                  previousTrend.value *
                  100
                : null;

        const frequency = [...(pasca.frequency ?? [])]
            .map((x) => ({
                repeat_count: x.repeat_count,
                locations: n(x.locations),
            }))
            .sort((a, b) => b.locations - a.locations);

        const repeat6 =
            frequency.find((x) => x.repeat_count >= 6)?.locations ?? 0;

        const repeatBurden =
            pasca.repeat_locations > 0
                ? pasca.repeat_occurrences / pasca.repeat_locations
                : 0;

        const priorityClassification = [
            ...(ds.priority_by_classification ?? []),
        ].sort((a, b) => n(b.priority_score) - n(a.priority_score));

        const priorityUnitap = [
            ...(ds.priority_by_unitap ?? []),
        ].sort((a, b) => n(b.priority_score) - n(a.priority_score));

        const coverage = ds.inspection_coverage ?? emptyDataScience().inspection_coverage;
        const repeatIntensity = ds.repeat_intensity ?? emptyDataScience().repeat_intensity;
        const concentration = ds.concentration ?? emptyDataScience().concentration;

        const praPasca = ds.pra_pasca_classification ?? [];

        const praTotal = praPasca
            .filter((x) => x.customer_type.toUpperCase() === "PRA")
            .reduce((sum, x) => sum + n(x.total), 0);

        const pascaTotal = praPasca
            .filter((x) => x.customer_type.toUpperCase() === "PASCA")
            .reduce((sum, x) => sum + n(x.total), 0);

        const highestPasca = Array.from(
            new Set(praPasca.map((x) => x.classification)),
        )
            .map((classification) => {
                const pra = praPasca.find(
                    (x) =>
                        x.classification === classification &&
                        x.customer_type.toUpperCase() === "PRA",
                )?.total ?? 0;

                const pascaValue = praPasca.find(
                    (x) =>
                        x.classification === classification &&
                        x.customer_type.toUpperCase() === "PASCA",
                )?.total ?? 0;

                const total = n(pra) + n(pascaValue);

                return {
                    classification,
                    pra: n(pra),
                    pasca: n(pascaValue),
                    share: total > 0 ? n(pascaValue) / total * 100 : 0,
                };
            })
            .sort((a, b) => b.share - a.share)[0] ?? null;

        return {
            classifications,
            ulps,
            heatmap,
            totalClassification,
            top3Share: totalClassification > 0
                ? top3 / totalClassification * 100
                : 0,
            topClass,
            topUlp,
            topUlpShare: suspect > 0 && topUlp
                ? topUlp.value / suspect * 100
                : 0,
            topHeatmap,
            findingRate,
            trend,
            latestTrend,
            previousTrend,
            trendDeltaPct,
            frequency,
            repeat6,
            repeatBurden,
            priorityClassification,
            priorityUnitap,
            coverage,
            repeatIntensity,
            concentration,
            praTotal,
            pascaTotal,
            praPascaShare:
                praTotal + pascaTotal > 0
                    ? pascaTotal / (praTotal + pascaTotal) * 100
                    : 0,
            highestPasca,
        };
    }, [charts, ds, kpi, pasca]);

    // ------------------------------------------------------
    // CHARTS
    // ------------------------------------------------------

    const classificationOption = useMemo(
        () =>
            horizontalBar(
                insight.classifications,
                C.accent,
                9,
            ),
        [insight.classifications],
    );

    const rankingOption = useMemo(
        () =>
            horizontalBar(
                insight.ulps,
                C.warning,
                10,
            ),
        [insight.ulps],
    );

    const heatmap = useMemo(
        () => heatmapOption(charts.heatmap_unitap_x_category ?? []),
        [charts.heatmap_unitap_x_category],
    );

    const repeatFrequency = useMemo(
        () =>
            horizontalBar(
                (pasca.frequency ?? []).map((x) => ({
                    label: `${x.repeat_count}×`,
                    value: n(x.locations),
                })),
                C.good,
                8,
            ),
        [pasca.frequency],
    );

    const repeatClassification = useMemo(
        () =>
            horizontalBar(
                (pasca.classification ?? []).map((x) => ({
                    label: x.classification,
                    value: n(x.repeat_locations),
                })),
                C.danger,
                9,
            ),
        [pasca.classification],
    );

    const monthly = useMemo(
        () => monthlyTrendOption(charts.monthly_trend ?? []),
        [charts.monthly_trend],
    );

    const praPasca = useMemo(
        () => praPasca100Option(ds.pra_pasca_classification ?? []),
        [ds.pra_pasca_classification],
    );

    const priorityClassificationOption = useMemo(
        () =>
            horizontalBar(
                insight.priorityClassification.map((item) => ({
                    label: item.classification,
                    value: n(item.priority_score),
                })),
                C.danger,
                10,
            ),
        [insight.priorityClassification],
    );

    const priorityUnitapOption = useMemo(
        () =>
            horizontalBar(
                insight.priorityUnitap.map((item) => ({
                    label: item.unitap,
                    value: n(item.priority_score),
                })),
                C.warning,
                10,
            ),
        [insight.priorityUnitap],
    );

    const concentrationOption = useMemo(
        () =>
            horizontalBar(
                insight.concentration.unitap.map((item) => ({
                    label: item.unitap,
                    value: n(item.share_pct),
                })),
                C.accent,
                10,
            ),
        [insight.concentration.unitap],
    );

    // ------------------------------------------------------
    // DATA SCIENCE
    // ------------------------------------------------------

    const dsCorrelation = useMemo(
        () => dataScienceCorrelationOption(ds.correlation ?? []),
        [ds.correlation],
    );

    const dsRegression = useMemo(
        () => dataScienceRegressionOption(ds.linear_regression ?? []),
        [ds.linear_regression],
    );

    const dsFeatureImportance = useMemo(
        () => dataScienceFeatureImportanceOption(ds.feature_importance ?? []),
        [ds.feature_importance],
    );

    const dsSummary = useMemo(() => {
        const correlations = [...(ds.correlation ?? [])].sort(
            (a, b) => n(b.abs_correlation) - n(a.abs_correlation),
        );
        const regressions = [...(ds.linear_regression ?? [])].sort(
            (a, b) => n(b.r_squared) - n(a.r_squared),
        );
        const importances = [...(ds.feature_importance ?? [])].sort(
            (a, b) => n(b.importance) - n(a.importance),
        );

        const strongestCorrelation = correlations[0] ?? null;
        const bestRegression = regressions[0] ?? null;
        const topFeature = importances[0] ?? null;

        const significancePool = [
            ...correlations.map((x) => x.significant ?? (x.p_value != null && n(x.p_value) <= 0.05)),
            ...regressions.map((x) => x.significant ?? (x.p_value != null && n(x.p_value) <= 0.05)),
        ];

        const significantCount = significancePool.filter(Boolean).length;
        const testedCount = significancePool.length;

        return {
            strongestCorrelation,
            bestRegression,
            topFeature,
            significantCount,
            testedCount,
        };
    }, [ds.correlation, ds.linear_regression, ds.feature_importance]);

    // ------------------------------------------------------
    // INITIAL LOAD
    // ------------------------------------------------------

    if (loadingMonths && !selectedMonth) {
        return (
            <div style={{ ...pageStyle, display: "grid", placeItems: "center" }}>
                Memuat Executive Dashboard...
            </div>
        );
    }

    if (error && !kpi && !loadingData) {
        return (
            <div style={pageStyle}>
                <div
                    style={{
                        ...cardStyle,
                        padding: 20,
                        color: C.warning,
                    }}
                >
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div style={pageStyle}>
            {/* ==================================================
                HEADER
            ================================================== */}

            <div
                style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: 18,
                    flexWrap: "wrap",
                    marginBottom: 24,
                }}
            >
                <div>
                    <h1
                        style={{
                            margin: 0,
                            fontSize: 30,
                            lineHeight: 1.15,
                            fontWeight: 850,
                        }}
                    >
                        Executive Dashboard
                    </h1>

                    <p
                        style={{
                            margin: "7px 0 0",
                            color: C.muted,
                            fontSize: 13,
                            lineHeight: 1.55,
                            maxWidth: 760,
                        }}
                    >
                        Dashboard ini menjawab tiga hal:{" "}
                        <strong style={{ color: C.text }}>
                            di mana risiko terbesar,
                        </strong>{" "}
                        <strong style={{ color: C.text }}>
                            jenis suspect apa yang dominan,
                        </strong>{" "}
                        dan{" "}
                        <strong style={{ color: C.text }}>
                            apakah kasus tersebut berulang.
                        </strong>
                    </p>
                </div>

                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 9,
                    }}
                >
                    <span
                        style={{
                            color: C.muted,
                            fontSize: 12,
                        }}
                    >
                        Periode
                    </span>

                    <select
                        aria-label="Pilih periode Executive Dashboard"
                        value={selectedMonth}
                        onChange={(event) => {
                            const next = event.target.value;
                            if (next && next !== selectedMonth) {
                                setSelectedMonth(next);
                            }
                        }}
                        disabled={loadingMonths || !months.length}
                        style={{
                            minWidth: 210,
                            padding: "10px 13px",
                            borderRadius: 9,
                            border: `1px solid ${C.border}`,
                            background: C.card,
                            color: C.text,
                            fontSize: 13,
                            cursor: loadingMonths ? "wait" : "pointer",
                            outline: "none",
                        }}
                    >
                        {!months.length ? (
                            <option value="">
                                {loadingMonths
                                    ? "Memuat bulan..."
                                    : "Tidak ada bulan"}
                            </option>
                        ) : null}

                        {months.map((month) => (
                            <option
                                key={month.month_key}
                                value={month.month_key}
                            >
                                {month.label} ({month.month_key})
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {error ? (
                <div
                    style={{
                        ...cardStyle,
                        padding: 12,
                        marginBottom: 18,
                        color: C.warning,
                        fontSize: 12,
                    }}
                >
                    {error}
                </div>
            ) : null}

            {loadingData ? (
                <div
                    style={{
                        ...cardStyle,
                        padding: "9px 13px",
                        marginBottom: 18,
                        color: C.accent,
                        fontSize: 12,
                    }}
                >
                    Memperbarui data untuk{" "}
                    <strong>
                        {monthLabel(months, selectedMonth)}
                    </strong>
                    ...
                </div>
            ) : null}

            {/* ==================================================
                1. EXECUTIVE SIGNAL
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Executive Signal</h2>

                <p style={sectionDescriptionStyle}>
                    Angka di sini dipilih untuk menjawab kondisi operasional,
                    bukan sekadar memenuhi dashboard.
                </p>

                <div style={gridFour}>
                    <KpiCard
                        title="Suspect Locations"
                        value={formatNumber(kpi?.total_suspects)}
                        description="populasi lokasi yang perlu diperhatikan"
                        tone="warning"
                    />

                    <KpiCard
                        title="Findings"
                        value={formatNumber(kpi?.total_findings)}
                        description={`${formatPercent(insight.findingRate)} dari suspect`}
                        tone={insight.findingRate >= 5 ? "danger" : "good"}
                    />

                    <KpiCard
                        title="Repeat Locations"
                        value={formatNumber(pasca.repeat_locations)}
                        description={`${formatPercent(pasca.repeat_rate_pct)} dari PASCA locations`}
                        tone="danger"
                    />

                    <KpiCard
                        title="Inspection Progress"
                        value={formatPercent(kpi?.progress_pct)}
                        description={`${formatNumber(kpi?.remaining_inspection)} customer tersisa`}
                        tone={n(kpi?.progress_pct) >= 80 ? "good" : "warning"}
                    />
                </div>
            </section>

            {/* ==================================================
                2. EXECUTIVE BRIEF
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Executive Brief</h2>

                <p style={sectionDescriptionStyle}>
                    Ringkasan yang langsung menunjuk objek prioritas.
                </p>

                <div style={gridTwo}>
                    <div
                        style={{
                            ...cardStyle,
                            padding: 18,
                            borderLeft: `3px solid ${C.danger}`,
                        }}
                    >
                        <div
                            style={{
                                color: C.muted,
                                fontSize: 11,
                                textTransform: "uppercase",
                                letterSpacing: 0.7,
                            }}
                        >
                            Prioritas utama
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                fontSize: 20,
                                fontWeight: 800,
                            }}
                        >
                            {insight.topClass?.label ?? "-"}
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                color: C.muted,
                                fontSize: 12,
                                lineHeight: 1.55,
                            }}
                        >
                            {insight.topClass
                                ? `${formatNumber(insight.topClass.value)} lokasi. Tiga klasifikasi terbesar menyumbang ${formatPercent(insight.top3Share)} dari seluruh volume klasifikasi.`
                                : "Belum ada data klasifikasi."}
                        </div>
                    </div>

                    <div
                        style={{
                            ...cardStyle,
                            padding: 18,
                            borderLeft: `3px solid ${C.warning}`,
                        }}
                    >
                        <div
                            style={{
                                color: C.muted,
                                fontSize: 11,
                                textTransform: "uppercase",
                                letterSpacing: 0.7,
                            }}
                        >
                            Prioritas wilayah
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                fontSize: 20,
                                fontWeight: 800,
                            }}
                        >
                            {insight.topUlp?.label ?? "-"}
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                color: C.muted,
                                fontSize: 12,
                                lineHeight: 1.55,
                            }}
                        >
                            {insight.topUlp
                                ? `${formatNumber(insight.topUlp.value)} suspect, sekitar ${formatPercent(insight.topUlpShare)} dari total suspect.`
                                : "Belum ada ranking ULP."}
                        </div>
                    </div>

                    <div
                        style={{
                            ...cardStyle,
                            padding: 18,
                            borderLeft: `3px solid ${C.good}`,
                        }}
                    >
                        <div
                            style={{
                                color: C.muted,
                                fontSize: 11,
                                textTransform: "uppercase",
                                letterSpacing: 0.7,
                            }}
                        >
                            Persistence
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                fontSize: 20,
                                fontWeight: 800,
                            }}
                        >
                            {formatPercent(pasca.repeat_rate_pct)}
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                color: C.muted,
                                fontSize: 12,
                                lineHeight: 1.55,
                            }}
                        >
                            lokasi PASCA yang berulang.{" "}
                            {insight.repeat6 > 0
                                ? `${formatNumber(insight.repeat6)} lokasi masuk kelompok frekuensi tertinggi yang tersedia.`
                                : "Belum ada distribusi frekuensi."}
                        </div>
                    </div>

                    <div
                        style={{
                            ...cardStyle,
                            padding: 18,
                            borderLeft: `3px solid ${C.accent}`,
                        }}
                    >
                        <div
                            style={{
                                color: C.muted,
                                fontSize: 11,
                                textTransform: "uppercase",
                                letterSpacing: 0.7,
                            }}
                        >
                            Hotspot kombinasi
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                fontSize: 18,
                                fontWeight: 800,
                            }}
                        >
                            {insight.topHeatmap
                                ? `${insight.topHeatmap.unitap} × ${truncate(insight.topHeatmap.category, 30)}`
                                : "-"}
                        </div>

                        <div
                            style={{
                                marginTop: 7,
                                color: C.muted,
                                fontSize: 12,
                                lineHeight: 1.55,
                            }}
                        >
                            {insight.topHeatmap
                                ? `${formatNumber(insight.topHeatmap.value)} lokasi pada kombinasi tertinggi.`
                                : "Belum ada data heatmap."}
                        </div>
                    </div>
                </div>
            </section>

            {/* ==================================================
                3. WHERE / WHAT
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Where & What</h2>

                <p style={sectionDescriptionStyle}>
                    Gunakan dua grafik ini untuk menentukan{" "}
                    <strong>jenis risiko</strong> dan{" "}
                    <strong>lokasi yang harus diperiksa lebih dulu</strong>.
                </p>

                <div style={gridTwo}>
                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Suspect by Classification
                        </h3>

                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            Volume lokasi suspect per klasifikasi.
                        </p>

                        <ReactECharts
                            option={classificationOption}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 380,
                            }}
                        />
                    </div>

                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Suspect by ULP
                        </h3>

                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            Ranking wilayah berdasarkan volume suspect.
                        </p>

                        <ReactECharts
                            option={rankingOption}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 380,
                            }}
                        />
                    </div>
                </div>

                <div
                    style={{
                        ...chartCardStyle,
                        marginTop: 16,
                    }}
                >
                    <h3 style={{ margin: 0, fontSize: 15 }}>
                        Hotspot UNITAP × Classification
                    </h3>

                    <p
                        style={{
                            margin: "5px 0 8px",
                            color: C.muted,
                            fontSize: 11,
                        }}
                    >
                        Ini adalah chart paling operasional: cari kombinasi
                        wilayah + jenis suspect yang paling padat.
                    </p>

                    <ReactECharts
                        option={heatmap}
                        notMerge
                        lazyUpdate
                        style={{
                            width: "100%",
                            height: 430,
                        }}
                    />
                </div>
            </section>

            {/* ==================================================
                4. PERSISTENCE
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Persistence & Repeat</h2>

                <p style={sectionDescriptionStyle}>
                    Volume besar belum tentu masalah terbesar. Lokasi yang
                    muncul berulang menunjukkan backlog/risk persistence yang
                    lebih layak diprioritaskan.
                </p>

                <div style={gridFour}>
                    <KpiCard
                        title="Unique PASCA"
                        value={formatNumber(pasca.total_locations)}
                        description="lokasi unik sampai periode aktif"
                    />

                    <KpiCard
                        title="Repeat"
                        value={formatNumber(pasca.repeat_locations)}
                        description={`${formatPercent(pasca.repeat_rate_pct)} dari unique PASCA`}
                        tone="danger"
                    />

                    <KpiCard
                        title="Repeat Occurrences"
                        value={formatNumber(pasca.repeat_occurrences)}
                        description="kemunculan tambahan"
                    />

                    <KpiCard
                        title="Repeat Burden"
                        value={`${insight.repeatBurden.toFixed(1)}×`}
                        description="repeat occurrences per repeat location"
                        tone="warning"
                    />
                </div>

                <div
                    style={{
                        ...gridTwo,
                        marginTop: 16,
                    }}
                >
                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Frequency of Appearance
                        </h3>

                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            Distribusi berapa kali lokasi yang sama muncul
                            lintas periode.
                        </p>

                        <ReactECharts
                            option={repeatFrequency}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 350,
                            }}
                        />
                    </div>

                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Repeat by Classification
                        </h3>

                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            Klasifikasi yang paling banyak menyisakan lokasi
                            berulang.
                        </p>

                        <ReactECharts
                            option={repeatClassification}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 350,
                            }}
                        />
                    </div>
                </div>
            </section>

            {/* ==================================================
                5. PRA / PASCA
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>PRA vs PASCA</h2>

                <p style={sectionDescriptionStyle}>
                    Fokus pada komposisi jenis customer. Bagian ini membantu
                    membedakan apakah pola suspect lebih banyak berada pada
                    PRA atau PASCA.
                </p>

                <div style={gridTwo}>
                    <div style={chartCardStyle}>
                        <ReactECharts
                            option={praPasca}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 410,
                            }}
                        />
                    </div>

                    <div
                        style={{
                            ...cardStyle,
                            padding: 18,
                        }}
                    >
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Composition
                        </h3>

                        <div
                            style={{
                                marginTop: 14,
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: 10,
                            }}
                        >
                            <MiniMetric
                                label="PRA"
                                value={formatNumber(insight.praTotal)}
                                description="lokasi–classification pairs"
                            />

                            <MiniMetric
                                label="PASCA"
                                value={formatNumber(insight.pascaTotal)}
                                description="lokasi–classification pairs"
                            />
                        </div>

                        <div style={{ marginTop: 10 }}>
                            <MiniMetric
                                label="PASCA Share"
                                value={formatPercent(insight.praPascaShare)}
                                description="porsi PASCA terhadap seluruh pasangan"
                            />
                        </div>

                        {insight.highestPasca ? (
                            <div
                                style={{
                                    marginTop: 10,
                                    padding: 14,
                                    borderRadius: 10,
                                    background: C.cardAlt,
                                    border: `1px solid ${C.border}`,
                                    color: C.muted,
                                    fontSize: 12,
                                    lineHeight: 1.55,
                                }}
                            >
                                <strong style={{ color: C.text }}>
                                    Paling PASCA-heavy:
                                </strong>{" "}
                                {insight.highestPasca.classification} —{" "}
                                {formatPercent(insight.highestPasca.share)} PASCA.
                            </div>
                        ) : null}
                    </div>
                </div>
            </section>

            {/* ==================================================
                6. TREND
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Trend Context</h2>

                <p style={sectionDescriptionStyle}>
                    Trend dipakai sebagai konteks perubahan, bukan sebagai
                    satu-satunya dasar keputusan.
                </p>

                <div style={gridTwo}>
                    <div style={chartCardStyle}>
                        <ReactECharts
                            option={monthly}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 320,
                            }}
                        />
                    </div>

                    <div
                        style={{
                            ...cardStyle,
                            padding: 18,
                        }}
                    >
                        <div
                            style={{
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            PERUBAHAN TERAKHIR
                        </div>

                        <div
                            style={{
                                marginTop: 8,
                                fontSize: 29,
                                fontWeight: 850,
                            }}
                        >
                            {insight.trendDeltaPct == null
                                ? "-"
                                : `${insight.trendDeltaPct >= 0 ? "+" : ""}${insight.trendDeltaPct.toFixed(1)}%`}
                        </div>

                        <div
                            style={{
                                marginTop: 5,
                                color:
                                    insight.trendDeltaPct == null
                                        ? C.muted
                                        : insight.trendDeltaPct > 0
                                          ? C.danger
                                          : C.good,
                                fontSize: 12,
                            }}
                        >
                            dibanding titik bulan sebelumnya yang tersedia
                        </div>

                        <div
                            style={{
                                marginTop: 16,
                                display: "grid",
                                gap: 10,
                            }}
                        >
                            <MiniMetric
                                label="Titik terbaru"
                                value={
                                    insight.latestTrend
                                        ? formatNumber(insight.latestTrend.value)
                                        : "-"
                                }
                                description={
                                    insight.latestTrend?.label ?? "Tidak tersedia"
                                }
                            />

                            <MiniMetric
                                label="Titik sebelumnya"
                                value={
                                    insight.previousTrend
                                        ? formatNumber(insight.previousTrend.value)
                                        : "-"
                                }
                                description={
                                    insight.previousTrend?.label ?? "Tidak tersedia"
                                }
                            />
                        </div>
                    </div>
                </div>
            </section>

            {/* ==================================================
                7. ANALYTICAL EVIDENCE
            ================================================== */}
            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Analytical Evidence</h2>

                <p style={sectionDescriptionStyle}>
                    Evidence analitis diturunkan langsung dari data Executive
                    yang tersedia: prioritas klasifikasi, prioritas UNITAP,
                    cakupan pemeriksaan, persistence, dan konsentrasi wilayah.
                    Model statistik/ML tidak ditampilkan jika memang belum
                    tersedia dari repository.
                </p>

                <div style={gridFour}>
                    <KpiCard
                        title="Inspection Coverage"
                        value={formatPercent(insight.coverage.coverage_pct)}
                        description={`${formatNumber(insight.coverage.inspected)} diperiksa dari ${formatNumber(insight.coverage.total_population)} populasi`}
                        tone={insight.coverage.coverage_pct >= 80 ? "good" : "warning"}
                    />

                    <KpiCard
                        title="Finding Rate"
                        value={formatPercent(insight.coverage.finding_rate_pct)}
                        description={`${formatNumber(insight.coverage.findings)} finding dari lokasi yang diperiksa`}
                        tone={insight.coverage.finding_rate_pct >= 5 ? "danger" : "good"}
                    />

                    <KpiCard
                        title="Repeat Intensity"
                        value={`${n(insight.repeatIntensity.avg_repeat_occurrences_per_repeat_location).toFixed(1)}×`}
                        description={`${formatNumber(insight.repeatIntensity.repeat_locations)} lokasi berulang`}
                        tone="danger"
                    />

                    <KpiCard
                        title="Top 3 UNITAP Share"
                        value={formatPercent(insight.concentration.top_3_share_pct)}
                        description={
                            insight.concentration.top_unitap
                                ? `terbesar: ${insight.concentration.top_unitap.unitap}`
                                : "Belum ada konsentrasi UNITAP"
                        }
                        tone="warning"
                    />
                </div>

                <div
                    style={{
                        ...gridTwo,
                        marginTop: 16,
                    }}
                >
                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Priority by Classification
                        </h3>
                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            Skor prioritas menggabungkan exposure PRA, exposure
                            PASCA, dan persistence/repeat.
                        </p>
                        <ReactECharts
                            option={priorityClassificationOption}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 360,
                            }}
                        />
                    </div>

                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Priority by UNITAP
                        </h3>
                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            UNITAP dengan kombinasi exposure PRA dan repeat
                            intensity tertinggi.
                        </p>
                        <ReactECharts
                            option={priorityUnitapOption}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 360,
                            }}
                        />
                    </div>
                </div>

                <div
                    style={{
                        ...gridTwo,
                        marginTop: 16,
                    }}
                >
                    <div style={chartCardStyle}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            UNITAP Concentration
                        </h3>
                        <p
                            style={{
                                margin: "5px 0 8px",
                                color: C.muted,
                                fontSize: 11,
                            }}
                        >
                            Pangsa populasi lokasi suspect pada periode aktif
                            berdasarkan UNITAP.
                        </p>
                        <ReactECharts
                            option={concentrationOption}
                            notMerge
                            lazyUpdate
                            style={{
                                width: "100%",
                                height: 360,
                            }}
                        />
                    </div>

                    <div style={{ ...cardStyle, padding: 18 }}>
                        <h3 style={{ margin: 0, fontSize: 15 }}>
                            Coverage & Persistence
                        </h3>

                        <div
                            style={{
                                marginTop: 14,
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: 10,
                            }}
                        >
                            <MiniMetric
                                label="Population"
                                value={formatNumber(insight.coverage.total_population)}
                                description="lokasi yang menjadi basis coverage"
                            />
                            <MiniMetric
                                label="Inspected"
                                value={formatNumber(insight.coverage.inspected)}
                                description="lokasi yang sudah diperiksa"
                            />
                            <MiniMetric
                                label="Remaining"
                                value={formatNumber(insight.coverage.remaining)}
                                description="lokasi yang belum diperiksa"
                            />
                            <MiniMetric
                                label="Normal"
                                value={formatNumber(insight.coverage.normal)}
                                description="hasil pemeriksaan normal"
                            />
                            <MiniMetric
                                label="Repeat Locations"
                                value={formatNumber(insight.repeatIntensity.repeat_locations)}
                                description="lokasi PASCA yang berulang"
                            />
                            <MiniMetric
                                label="Repeat Occurrences"
                                value={formatNumber(insight.repeatIntensity.repeat_occurrences)}
                                description="kemunculan tambahan"
                            />
                            <MiniMetric
                                label="Max Repeat"
                                value={`${formatNumber(insight.repeatIntensity.max_repeat_count)}×`}
                                description="frekuensi maksimum yang tersedia"
                            />
                            <MiniMetric
                                label="Top UNITAP"
                                value={insight.concentration.top_unitap?.unitap ?? "-"}
                                description={
                                    insight.concentration.top_unitap
                                        ? `${formatPercent(insight.concentration.top_unitap.share_pct)} share`
                                        : "Belum ada data"
                                }
                            />
                        </div>
                    </div>
                </div>

                <div
                    style={{
                        ...cardStyle,
                        marginTop: 16,
                        padding: 18,
                    }}
                >
                    <h3 style={{ margin: 0, fontSize: 15 }}>
                        Analytical Reading
                    </h3>

                    <div
                        style={{
                            marginTop: 12,
                            display: "grid",
                            gap: 9,
                            color: C.muted,
                            fontSize: 12,
                            lineHeight: 1.55,
                        }}
                    >
                        <div>
                            <strong style={{ color: C.text }}>
                                Prioritas klasifikasi:
                            </strong>{" "}
                            {insight.priorityClassification[0]
                                ? `${insight.priorityClassification[0].classification} memiliki skor ${n(insight.priorityClassification[0].priority_score).toFixed(2)}.`
                                : "belum tersedia."}
                        </div>

                        <div>
                            <strong style={{ color: C.text }}>
                                Prioritas UNITAP:
                            </strong>{" "}
                            {insight.priorityUnitap[0]
                                ? `${insight.priorityUnitap[0].unitap} memiliki skor ${n(insight.priorityUnitap[0].priority_score).toFixed(2)} dengan ${formatNumber(insight.priorityUnitap[0].repeat_locations)} lokasi berulang.`
                                : "belum tersedia."}
                        </div>

                        <div>
                            <strong style={{ color: C.text }}>
                                Coverage:
                            </strong>{" "}
                            {`${formatPercent(insight.coverage.coverage_pct)} populasi sudah diperiksa, dengan ${formatNumber(insight.coverage.remaining)} lokasi tersisa.`}
                        </div>

                        <div>
                            <strong style={{ color: C.text }}>
                                Persistence:
                            </strong>{" "}
                            {`${formatPercent(insight.repeatIntensity.repeat_rate_pct)} lokasi PASCA berulang, dengan rata-rata ${n(insight.repeatIntensity.avg_repeat_occurrences_per_repeat_location).toFixed(1)} kemunculan tambahan per lokasi repeat.`}
                        </div>

                        <div>
                            <strong style={{ color: C.text }}>
                                Konsentrasi:
                            </strong>{" "}
                            {insight.concentration.top_unitap
                                ? `UNITAP ${insight.concentration.top_unitap.unitap} menyumbang ${formatPercent(insight.concentration.top_unitap.share_pct)} populasi, sementara tiga UNITAP teratas menyumbang ${formatPercent(insight.concentration.top_3_share_pct)}.`
                                : "belum tersedia."}
                        </div>
                    </div>
                </div>

                <div
                    style={{
                        ...cardStyle,
                        marginTop: 16,
                        padding: 18,
                        background: C.cardAlt,
                    }}
                >
                    <div
                        style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            gap: 14,
                            flexWrap: "wrap",
                        }}
                    >
                        <div>
                            <div
                                style={{
                                    color: C.accent,
                                    fontSize: 10,
                                    fontWeight: 800,
                                    textTransform: "uppercase",
                                    letterSpacing: 1,
                                }}
                            >
                                Statistical Layer
                            </div>
                            <h3 style={{ margin: "5px 0 0", fontSize: 18 }}>
                                Data Science: Faktor & Hubungan
                            </h3>
                            <p
                                style={{
                                    margin: "6px 0 0",
                                    color: C.muted,
                                    fontSize: 12,
                                    lineHeight: 1.55,
                                    maxWidth: 760,
                                }}
                            >
                                Bagian ini menjawab faktor apa yang berkaitan dengan
                                suspect, seberapa kuat hubungannya, dan apakah
                                hubungan/model tersebut signifikan secara statistik.
                            </p>
                        </div>

                        <div
                            style={{
                                padding: "8px 11px",
                                borderRadius: 9,
                                border: `1px solid ${C.border}`,
                                background: C.card,
                                color: C.muted,
                                fontSize: 10,
                                whiteSpace: "nowrap",
                            }}
                        >
                            α = 0,05
                        </div>
                    </div>

                    <div style={{ ...gridFour, marginTop: 16 }}>
                        <KpiCard
                            title="Strongest Correlation"
                            value={
                                dsSummary.strongestCorrelation
                                    ? n(dsSummary.strongestCorrelation.correlation).toFixed(3)
                                    : "-"
                            }
                            description={
                                dsSummary.strongestCorrelation
                                    ? `${truncate(dsSummary.strongestCorrelation.feature_x, 28)} · |r| ${n(dsSummary.strongestCorrelation.abs_correlation).toFixed(3)}`
                                    : "Belum ada data correlation"
                            }
                            tone={
                                dsSummary.strongestCorrelation
                                    ? significanceTone(
                                          dsSummary.strongestCorrelation.p_value,
                                          dsSummary.strongestCorrelation.significant,
                                      )
                                    : "normal"
                            }
                        />

                        <KpiCard
                            title="Best Regression"
                            value={
                                dsSummary.bestRegression
                                    ? `R² ${n(dsSummary.bestRegression.r_squared).toFixed(3)}`
                                    : "-"
                            }
                            description={
                                dsSummary.bestRegression
                                    ? `${truncate(dsSummary.bestRegression.feature, 28)} → ${truncate(dsSummary.bestRegression.target, 24)}`
                                    : "Belum ada model regression"
                            }
                            tone={
                                dsSummary.bestRegression
                                    ? significanceTone(
                                          dsSummary.bestRegression.p_value,
                                          dsSummary.bestRegression.significant,
                                      )
                                    : "normal"
                            }
                        />

                        <KpiCard
                            title="Top Feature"
                            value={
                                dsSummary.topFeature
                                    ? truncate(dsSummary.topFeature.feature, 25)
                                    : "-"
                            }
                            description={
                                dsSummary.topFeature
                                    ? `importance ${n(dsSummary.topFeature.importance).toFixed(3)} · ${dsSummary.topFeature.direction ?? "direction N/A"}`
                                    : "Belum ada feature importance"
                            }
                            tone="good"
                        />

                        <KpiCard
                            title="Model Significance"
                            value={
                                dsSummary.testedCount > 0
                                    ? `${dsSummary.significantCount}/${dsSummary.testedCount}`
                                    : "N/A"
                            }
                            description={
                                dsSummary.testedCount > 0
                                    ? "uji p-value yang signifikan pada α = 0,05"
                                    : "Belum ada p-value model"
                            }
                            tone={
                                dsSummary.significantCount > 0
                                    ? "good"
                                    : dsSummary.testedCount > 0
                                      ? "warning"
                                      : "normal"
                            }
                        />
                    </div>

                    <div style={{ ...gridTwo, marginTop: 16 }}>
                        <div style={chartCardStyle}>
                            <h3 style={{ margin: 0, fontSize: 15 }}>
                                Correlation: Variabel yang Paling Berkaitan
                            </h3>
                            <p
                                style={{
                                    margin: "5px 0 8px",
                                    color: C.muted,
                                    fontSize: 11,
                                }}
                            >
                                Positif berarti bergerak searah; negatif berlawanan.
                                Correlation bukan bukti sebab-akibat.
                            </p>
                            <ReactECharts
                                option={dsCorrelation}
                                notMerge
                                lazyUpdate
                                style={{
                                    width: "100%",
                                    height: 410,
                                }}
                            />
                        </div>

                        <div style={chartCardStyle}>
                            <h3 style={{ margin: 0, fontSize: 15 }}>
                                Regression: Seberapa Banyak Variasi Dijelaskan?
                            </h3>
                            <p
                                style={{
                                    margin: "5px 0 8px",
                                    color: C.muted,
                                    fontSize: 11,
                                }}
                            >
                                R² menunjukkan proporsi variasi target yang
                                dijelaskan model; p-value digunakan untuk menilai
                                signifikansi statistik.
                            </p>
                            <ReactECharts
                                option={dsRegression}
                                notMerge
                                lazyUpdate
                                style={{
                                    width: "100%",
                                    height: 410,
                                }}
                            />
                        </div>
                    </div>

                    <div style={{ ...gridTwo, marginTop: 16 }}>
                        <div style={chartCardStyle}>
                            <h3 style={{ margin: 0, fontSize: 15 }}>
                                Feature Importance: Faktor Paling Berpengaruh
                            </h3>
                            <p
                                style={{
                                    margin: "5px 0 8px",
                                    color: C.muted,
                                    fontSize: 11,
                                }}
                            >
                                Ranking kontribusi relatif feature terhadap target
                                model. Ini bukan p-value dan bukan bukti hubungan
                                sebab-akibat.
                            </p>
                            <ReactECharts
                                option={dsFeatureImportance}
                                notMerge
                                lazyUpdate
                                style={{
                                    width: "100%",
                                    height: 410,
                                }}
                            />
                        </div>

                        <div style={{ ...cardStyle, padding: 18 }}>
                            <h3 style={{ margin: 0, fontSize: 15 }}>
                                Cara Membaca Hasil Statistik
                            </h3>

                            <div
                                style={{
                                    marginTop: 12,
                                    display: "grid",
                                    gap: 10,
                                }}
                            >
                                {[
                                    {
                                        code: "r",
                                        title: "Correlation",
                                        text: "Semakin dekat ke +1 atau −1, semakin kuat hubungan linear. Nilai mendekati 0 berarti hubungan linear lemah.",
                                    },
                                    {
                                        code: "R²",
                                        title: "Regression",
                                        text: "Semakin besar R², semakin besar proporsi variasi target yang dijelaskan oleh model.",
                                    },
                                    {
                                        code: "p",
                                        title: "Significance",
                                        text: "p-value ≤ 0,05 diperlakukan signifikan pada ambang α = 0,05. Signifikan tidak otomatis berarti sebab-akibat.",
                                    },
                                    {
                                        code: "FI",
                                        title: "Feature Importance",
                                        text: "Importance menunjukkan kontribusi relatif feature dalam model. Jangan membacanya sebagai koefisien kausal.",
                                    },
                                ].map((item) => (
                                    <div
                                        key={item.code}
                                        style={{
                                            display: "grid",
                                            gridTemplateColumns: "34px 1fr",
                                            gap: 10,
                                            padding: 12,
                                            borderRadius: 10,
                                            background: C.card,
                                            border: `1px solid ${C.border}`,
                                        }}
                                    >
                                        <div
                                            style={{
                                                width: 30,
                                                height: 30,
                                                display: "grid",
                                                placeItems: "center",
                                                borderRadius: 8,
                                                background: C.cardAlt,
                                                border: `1px solid ${C.border}`,
                                                color: C.accent,
                                                fontSize: 10,
                                                fontWeight: 800,
                                            }}
                                        >
                                            {item.code}
                                        </div>
                                        <div>
                                            <div
                                                style={{
                                                    color: C.text,
                                                    fontSize: 12,
                                                    fontWeight: 800,
                                                }}
                                            >
                                                {item.title}
                                            </div>
                                            <div
                                                style={{
                                                    marginTop: 3,
                                                    color: C.muted,
                                                    fontSize: 11,
                                                    lineHeight: 1.5,
                                                }}
                                            >
                                                {item.text}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div
                                style={{
                                    marginTop: 10,
                                    padding: 12,
                                    borderRadius: 10,
                                    border: `1px solid ${C.border}`,
                                    background: C.cardAlt,
                                    color: C.muted,
                                    fontSize: 11,
                                    lineHeight: 1.5,
                                }}
                            >
                                <strong style={{ color: C.text }}>
                                    Catatan interpretasi:
                                </strong>{" "}
                                hasil statistik dibaca sebagai evidence pendukung.
                                Prioritas operasional tetap perlu dilihat bersama
                                exposure, persistence/repeat, coverage, dan konteks
                                wilayah.
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ==================================================
                8. DATA QUALITY / PERIOD CHECK
            ================================================== */}

            <section style={sectionStyle}>
                <h2 style={sectionTitleStyle}>Period & Data Check</h2>

                <div
                    style={{
                        ...cardStyle,
                        padding: 18,
                    }}
                >
                    <div style={gridFour}>
                        <MiniMetric
                            label="Selected Month"
                            value={selectedMonth || "-"}
                            description={monthLabel(months, selectedMonth)}
                        />

                        <MiniMetric
                            label="Customers"
                            value={formatNumber(kpi?.total_customers)}
                            description="populasi customer"
                        />

                        <MiniMetric
                            label="Normal"
                            value={formatNumber(kpi?.total_normal)}
                            description="customer normal"
                        />

                        <MiniMetric
                            label="Findings"
                            value={formatNumber(kpi?.total_findings)}
                            description="temuan pada periode aktif"
                        />
                    </div>

                    <div
                        style={{
                            marginTop: 14,
                            padding: 12,
                            borderRadius: 10,
                            background: C.cardAlt,
                            border: `1px solid ${C.border}`,
                            color: C.muted,
                            fontSize: 11,
                            lineHeight: 1.55,
                        }}
                    >
                        Dropdown periode sekarang hanya menggunakan daftar
                        bulan yang benar-benar dikembalikan endpoint{" "}
                        <strong style={{ color: C.text }}>
                            /executive/months
                        </strong>
                        . Saat periode diganti, request KPI dan charts
                        dikirim ulang dengan query{" "}
                        <strong style={{ color: C.text }}>
                            month={selectedMonth || "-"}
                        </strong>
                        .
                    </div>
                </div>
            </section>

            <div
                style={{
                    ...cardStyle,
                    padding: "11px 14px",
                    color: C.muted,
                    fontSize: 11,
                }}
            >
                Periode aktif:{" "}
                <strong style={{ color: C.text }}>
                    {monthLabel(months, selectedMonth)}
                </strong>

                {loadingData ? (
                    <span> · Memperbarui data...</span>
                ) : (
                    <span> · Data termuat</span>
                )}
            </div>
        </div>
    );
}
