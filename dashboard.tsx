import { useEffect, useMemo, useState } from "react";

type ChartPoint = {
  label: string;
  value: number;
};

type HeatmapPoint = {
  unitap: string;
  category: string;
  value: number;
};

type PraClassification = {
  classification: string;
  total: number;
};

type PraUnitap = {
  unitap: string;
  total: number;
};

type PraMonthly = {
  total_locations: number;
  total_classifications: number;
  classification: PraClassification[];
  unitap: PraUnitap[];
};

type PascaFrequency = {
  repeat_count: number;
  locations: number;
};

type PascaClassification = {
  classification: string;
  total_locations: number;
  repeat_locations: number;
  repeat_occurrences: number;
};

type PascaRepeat = {
  total_locations: number;
  repeat_locations: number;
  repeat_occurrences: number;
  repeat_rate_pct: number;
  frequency: PascaFrequency[];
  classification: PascaClassification[];
};

type ExecutiveCharts = {
  bar_by_unitap: ChartPoint[];
  pie_by_tariff: ChartPoint[];
  donut_by_segment: ChartPoint[];
  monthly_trend: ChartPoint[];
  ranking_by_ulp: ChartPoint[];
  heatmap_unitap_x_category: HeatmapPoint[];

  anev_classification: ChartPoint[];
  anev_by_unitap: ChartPoint[];
  anev_by_tariff: ChartPoint[];

  pra_monthly: PraMonthly;
  pasca_repeat: PascaRepeat;

  repeat_cases: ChartPoint[];
};

type MonthOption = {
  month_key: string;
  label: string;
};

type ApiResponse<T> = {
  success: boolean;
  data: T;
};

const API_PREFIX = "/api/v1";


// ==========================================================
// HELPERS
// ==========================================================

function formatNumber(value: number): string {
  return new Intl.NumberFormat("id-ID").format(
    Number.isFinite(value) ? value : 0,
  );
}


function formatPercent(value: number): string {
  return `${Number(value || 0).toFixed(2)}%`;
}


function shortLabel(value: string, max = 25): string {
  if (!value) return "-";

  if (value.length <= max) {
    return value;
  }

  return `${value.slice(0, max - 3)}...`;
}


function monthLabel(month: MonthOption): string {
  if (month.label) {
    return month.label;
  }

  const value = month.month_key;

  if (!/^\d{6}$/.test(value)) {
    return value;
  }

  const year = value.slice(0, 4);
  const monthNumber = Number(value.slice(4, 6));

  const names = [
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

  return `${names[monthNumber - 1] || value} ${year}`;
}


// ==========================================================
// BASIC UI
// ==========================================================

function Card({
  children,
  title,
  subtitle,
}: {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
}) {
  return (
    <section className="exec-card">
      {(title || subtitle) && (
        <div className="exec-card-header">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p>{subtitle}</p>}
          </div>
        </div>
      )}

      {children}
    </section>
  );
}


function KpiCard({
  title,
  value,
  description,
}: {
  title: string;
  value: string;
  description: string;
}) {
  return (
    <div className="exec-kpi">
      <div className="exec-kpi-title">{title}</div>

      <div className="exec-kpi-value">
        {value}
      </div>

      <div className="exec-kpi-description">
        {description}
      </div>
    </div>
  );
}


// ==========================================================
// HORIZONTAL BAR CHART
// ==========================================================

function HorizontalBarChart({
  data,
  height = 360,
}: {
  data: ChartPoint[];
  height?: number;
}) {
  if (!data.length) {
    return <EmptyState />;
  }

  const max = Math.max(
    ...data.map((item) => item.value),
    1,
  );

  return (
    <div
      className="horizontal-chart"
      style={{ minHeight: height }}
    >
      {data.map((item) => {
        const percentage =
          (item.value / max) * 100;

        return (
          <div
            className="bar-row"
            key={item.label}
          >
            <div
              className="bar-label"
              title={item.label}
            >
              {shortLabel(item.label, 32)}
            </div>

            <div className="bar-track">
              <div
                className="bar-fill"
                style={{
                  width: `${percentage}%`,
                }}
              />
            </div>

            <div className="bar-value">
              {formatNumber(item.value)}
            </div>
          </div>
        );
      })}
    </div>
  );
}


// ==========================================================
// VERTICAL BAR CHART
// ==========================================================

function VerticalBarChart({
  data,
}: {
  data: ChartPoint[];
}) {
  if (!data.length) {
    return <EmptyState />;
  }

  const max = Math.max(
    ...data.map((item) => item.value),
    1,
  );

  return (
    <div className="vertical-chart">
      {data.map((item) => {
        const height =
          Math.max(
            (item.value / max) * 100,
            3,
          );

        return (
          <div
            className="vertical-bar-item"
            key={item.label}
            title={`${item.label}: ${formatNumber(item.value)}`}
          >
            <div className="vertical-value">
              {formatNumber(item.value)}
            </div>

            <div className="vertical-track">
              <div
                className="vertical-fill"
                style={{
                  height: `${height}%`,
                }}
              />
            </div>

            <div className="vertical-label">
              {item.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}


// ==========================================================
// TREND CHART
// ==========================================================

function TrendChart({
  data,
}: {
  data: ChartPoint[];
}) {
  if (!data.length) {
    return <EmptyState />;
  }

  const width = 760;
  const height = 280;
  const paddingLeft = 55;
  const paddingRight = 20;
  const paddingTop = 25;
  const paddingBottom = 45;

  const chartWidth =
    width - paddingLeft - paddingRight;

  const chartHeight =
    height - paddingTop - paddingBottom;

  const values = data.map(
    (item) => item.value,
  );

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);

  const range =
    maxValue - minValue || 1;

  const points = data.map(
    (item, index) => {
      const x =
        paddingLeft +
        (index /
          Math.max(data.length - 1, 1)) *
          chartWidth;

      const y =
        paddingTop +
        chartHeight -
        ((item.value - minValue) /
          range) *
          chartHeight;

      return {
        x,
        y,
        item,
      };
    },
  );

  const path = points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`,
    )
    .join(" ");

  return (
    <div className="trend-wrapper">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="trend-svg"
        preserveAspectRatio="none"
      >
        {[0, 1, 2, 3, 4].map(
          (grid) => {
            const y =
              paddingTop +
              (grid / 4) *
                chartHeight;

            return (
              <line
                key={grid}
                x1={paddingLeft}
                x2={
                  width -
                  paddingRight
                }
                y1={y}
                y2={y}
                className="trend-grid"
              />
            );
          },
        )}

        <path
          d={path}
          fill="none"
          className="trend-line"
        />

        {points.map(
          (point) => (
            <g
              key={point.item.label}
            >
              <circle
                cx={point.x}
                cy={point.y}
                r="4"
                className="trend-point"
              />

              <text
                x={point.x}
                y={
                  height -
                  18
                }
                textAnchor="middle"
                className="trend-label"
              >
                {point.item.label.slice(
                  4,
                )}
              </text>
            </g>
          ),
        )}
      </svg>

      <div className="trend-summary">
        <span>
          Terendah:{" "}
          <strong>
            {formatNumber(
              minValue,
            )}
          </strong>
        </span>

        <span>
          Tertinggi:{" "}
          <strong>
            {formatNumber(
              maxValue,
            )}
          </strong>
        </span>
      </div>
    </div>
  );
}


// ==========================================================
// REPEAT FREQUENCY
// ==========================================================

function RepeatFrequencyChart({
  data,
}: {
  data: PascaFrequency[];
}) {
  if (!data.length) {
    return <EmptyState />;
  }

  const max = Math.max(
    ...data.map(
      (item) => item.locations,
    ),
    1,
  );

  return (
    <div className="repeat-chart">
      {data.map((item) => {
        const percentage =
          (item.locations / max) *
          100;

        return (
          <div
            className="repeat-row"
            key={item.repeat_count}
          >
            <div className="repeat-count">
              {item.repeat_count}x
            </div>

            <div className="bar-track">
              <div
                className="bar-fill repeat-fill"
                style={{
                  width: `${percentage}%`,
                }}
              />
            </div>

            <div className="bar-value">
              {formatNumber(
                item.locations,
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}


// ==========================================================
// CLASSIFICATION TABLE
// ==========================================================

function RepeatClassificationTable({
  data,
}: {
  data: PascaClassification[];
}) {
  if (!data.length) {
    return <EmptyState />;
  }

  return (
    <div className="table-wrapper">
      <table className="exec-table">
        <thead>
          <tr>
            <th>Klasifikasi</th>
            <th>Total Lokasi</th>
            <th>Berulang</th>
            <th>Repeat Occurrence</th>
            <th>Repeat Rate</th>
          </tr>
        </thead>

        <tbody>
          {data.map((item) => {
            const rate =
              item.total_locations
                ? (item.repeat_locations /
                    item.total_locations) *
                  100
                : 0;

            return (
              <tr
                key={
                  item.classification
                }
              >
                <td
                  title={
                    item.classification
                  }
                >
                  {shortLabel(
                    item.classification,
                    42,
                  )}
                </td>

                <td>
                  {formatNumber(
                    item.total_locations,
                  )}
                </td>

                <td>
                  {formatNumber(
                    item.repeat_locations,
                  )}
                </td>

                <td>
                  {formatNumber(
                    item.repeat_occurrences,
                  )}
                </td>

                <td>
                  {formatPercent(rate)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


// ==========================================================
// HEATMAP
// ==========================================================

function Heatmap({
  data,
}: {
  data: HeatmapPoint[];
}) {
  const unitaps = useMemo(
    () =>
      Array.from(
        new Set(
          data.map(
            (item) => item.unitap,
          ),
        ),
      ),
    [data],
  );

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          data.map(
            (item) => item.category,
          ),
        ),
      ),
    [data],
  );

  const lookup = useMemo(() => {
    const map = new Map<
      string,
      number
    >();

    data.forEach((item) => {
      map.set(
        `${item.unitap}|||${item.category}`,
        item.value,
      );
    });

    return map;
  }, [data]);

  const max = Math.max(
    ...data.map(
      (item) => item.value,
    ),
    1,
  );

  if (
    !unitaps.length ||
    !categories.length
  ) {
    return <EmptyState />;
  }

  return (
    <div className="heatmap-wrapper">
      <div
        className="heatmap-grid"
        style={{
          gridTemplateColumns: `180px repeat(${unitaps.length}, minmax(100px, 1fr))`,
        }}
      >
        <div className="heatmap-corner">
          Klasifikasi
        </div>

        {unitaps.map(
          (unitap) => (
            <div
              className="heatmap-header"
              key={unitap}
            >
              {unitap}
            </div>
          ),
        )}

        {categories.map(
          (category) => (
            <div
              className="heatmap-row"
              key={category}
            >
              <div
                className="heatmap-category"
                title={category}
              >
                {shortLabel(
                  category,
                  30,
                )}
              </div>

              {unitaps.map(
                (unitap) => {
                  const value =
                    lookup.get(
                      `${unitap}|||${category}`,
                    ) || 0;

                  const opacity =
                    value / max;

                  return (
                    <div
                      className="heatmap-cell"
                      key={`${unitap}-${category}`}
                      title={`${unitap} — ${category}: ${formatNumber(value)}`}
                      style={{
                        opacity:
                          Math.max(
                            opacity,
                            0.08,
                          ),
                      }}
                    >
                      {formatNumber(
                        value,
                      )}
                    </div>
                  );
                },
              )}
            </div>
          ),
        )}
      </div>
    </div>
  );
}


// ==========================================================
// EMPTY
// ==========================================================

function EmptyState() {
  return (
    <div className="empty-state">
      Tidak ada data.
    </div>
  );
}


// ==========================================================
// LOADING
// ==========================================================

function LoadingState() {
  return (
    <div className="loading-state">
      <div className="loading-spinner" />
      <span>
        Memuat Executive Dashboard...
      </span>
    </div>
  );
}


// ==========================================================
// MAIN DASHBOARD
// ==========================================================

export default function Dashboard() {
  const [months, setMonths] =
    useState<MonthOption[]>([]);

  const [month, setMonth] =
    useState("");

  const [data, setData] =
    useState<ExecutiveCharts | null>(
      null,
    );

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  // ========================================================
  // LOAD MONTHS
  // ========================================================

  useEffect(() => {
    let mounted = true;

    async function loadMonths() {
      try {
        const response =
          await fetch(
            `${API_PREFIX}/executive/months`,
            {
              credentials: "include",
            },
          );

        if (!response.ok) {
          throw new Error(
            `Gagal mengambil daftar bulan (${response.status})`,
          );
        }

        const payload =
          (await response.json()) as ApiResponse<
            MonthOption[]
          >;

        if (!mounted) {
          return;
        }

        const available =
          payload.data || [];

        setMonths(
          available,
        );

        if (
          available.length
        ) {
          setMonth(
            available[
              available.length - 1
            ].month_key,
          );
        }
      } catch (err) {
        if (!mounted) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Gagal mengambil bulan Executive.",
        );

        setLoading(false);
      }
    }

    loadMonths();

    return () => {
      mounted = false;
    };
  }, []);


  // ========================================================
  // LOAD EXECUTIVE DATA
  // ========================================================

  useEffect(() => {
    if (!month) {
      return;
    }

    let mounted = true;

    async function loadExecutive() {
      setLoading(true);
      setError(null);

      try {
        const response =
          await fetch(
            `${API_PREFIX}/executive/charts?month=${encodeURIComponent(month)}`,
            {
              credentials: "include",
            },
          );

        if (!response.ok) {
          throw new Error(
            `Gagal mengambil data Executive (${response.status})`,
          );
        }

        const payload =
          (await response.json()) as ApiResponse<
            ExecutiveCharts
          >;

        if (!mounted) {
          return;
        }

        setData(
          payload.data,
        );
      } catch (err) {
        if (!mounted) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Gagal mengambil data Executive.",
        );

        setData(null);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadExecutive();

    return () => {
      mounted = false;
    };
  }, [month]);


  // ========================================================
  // DERIVED DATA
  // ========================================================

  const pra =
    data?.pra_monthly || {
      total_locations: 0,
      total_classifications: 0,
      classification: [],
      unitap: [],
    };

  const pasca =
    data?.pasca_repeat || {
      total_locations: 0,
      repeat_locations: 0,
      repeat_occurrences: 0,
      repeat_rate_pct: 0,
      frequency: [],
      classification: [],
    };

  const classification =
    data?.anev_classification ||
    [];

  const unitap =
    data?.anev_by_unitap ||
    [];

  const tariff =
    data?.anev_by_tariff ||
    [];

  const trend =
    data?.monthly_trend ||
    [];

  const ulp =
    data?.ranking_by_ulp ||
    [];

  const heatmap =
    data?.heatmap_unitap_x_category ||
    [];


  // ========================================================
  // RENDER
  // ========================================================

  return (
    <div className="executive-dashboard">
      <style>{`
        * {
          box-sizing: border-box;
        }

        .executive-dashboard {
          min-height: 100vh;
          padding: 28px;
          background: #f5f7fb;
          color: #18212f;
          font-family:
            Inter,
            ui-sans-serif,
            system-ui,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
        }

        .exec-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 26px;
        }

        .exec-title {
          margin: 0;
          font-size: 28px;
          font-weight: 750;
          letter-spacing: -0.5px;
        }

        .exec-subtitle {
          margin: 7px 0 0;
          color: #697586;
          font-size: 14px;
        }

        .month-selector {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 10px;
          background: #ffffff;
          border: 1px solid #e3e8ef;
          border-radius: 10px;
          box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
        }

        .month-selector label {
          font-size: 12px;
          font-weight: 650;
          color: #697586;
        }

        .month-selector select {
          border: 0;
          outline: none;
          background: transparent;
          color: #18212f;
          font-size: 14px;
          font-weight: 650;
          cursor: pointer;
        }

        .exec-kpi-grid {
          display: grid;
          grid-template-columns:
            repeat(4, minmax(0, 1fr));
          gap: 16px;
          margin-bottom: 18px;
        }

        .exec-kpi {
          padding: 20px;
          background: #ffffff;
          border: 1px solid #e3e8ef;
          border-radius: 14px;
          box-shadow:
            0 3px 12px
            rgba(16, 24, 40, 0.045);
        }

        .exec-kpi-title {
          font-size: 13px;
          font-weight: 600;
          color: #697586;
        }

        .exec-kpi-value {
          margin-top: 9px;
          font-size: 28px;
          line-height: 1.1;
          font-weight: 760;
          letter-spacing: -0.6px;
        }

        .exec-kpi-description {
          margin-top: 8px;
          font-size: 12px;
          color: #8a95a5;
        }

        .exec-grid-2 {
          display: grid;
          grid-template-columns:
            minmax(0, 1.5fr)
            minmax(0, 1fr);
          gap: 18px;
          margin-bottom: 18px;
        }

        .exec-grid-3 {
          display: grid;
          grid-template-columns:
            repeat(3, minmax(0, 1fr));
          gap: 18px;
          margin-bottom: 18px;
        }

        .exec-card {
          background: #ffffff;
          border: 1px solid #e3e8ef;
          border-radius: 14px;
          padding: 20px;
          box-shadow:
            0 3px 12px
            rgba(16, 24, 40, 0.045);
          overflow: hidden;
        }

        .exec-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 18px;
        }

        .exec-card-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 720;
        }

        .exec-card-header p {
          margin: 5px 0 0;
          color: #8a95a5;
          font-size: 12px;
        }

        .horizontal-chart {
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 13px;
        }

        .bar-row {
          display: grid;
          grid-template-columns:
            180px
            minmax(100px, 1fr)
            80px;
          align-items: center;
          gap: 12px;
        }

        .bar-label {
          font-size: 12px;
          font-weight: 600;
          color: #465365;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .bar-track {
          height: 9px;
          overflow: hidden;
          border-radius: 999px;
          background: #edf1f5;
        }

        .bar-fill {
          height: 100%;
          border-radius: inherit;
          background: #2563eb;
          transition: width 0.3s ease;
        }

        .bar-value {
          text-align: right;
          font-size: 12px;
          font-weight: 700;
          color: #293548;
        }

        .vertical-chart {
          height: 300px;
          display: flex;
          align-items: flex-end;
          gap: 14px;
          padding:
            10px
            8px
            0;
          overflow-x: auto;
        }

        .vertical-bar-item {
          min-width: 55px;
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: flex-end;
          align-items: center;
          gap: 7px;
        }

        .vertical-value {
          font-size: 10px;
          font-weight: 700;
          color: #526071;
          white-space: nowrap;
        }

        .vertical-track {
          width: 30px;
          height: 220px;
          display: flex;
          align-items: flex-end;
          overflow: hidden;
          border-radius: 7px 7px 3px 3px;
          background: #edf1f5;
        }

        .vertical-fill {
          width: 100%;
          border-radius: 7px 7px 3px 3px;
          background: #2563eb;
        }

        .vertical-label {
          font-size: 11px;
          font-weight: 650;
          color: #526071;
        }

        .trend-wrapper {
          width: 100%;
        }

        .trend-svg {
          width: 100%;
          height: 280px;
          overflow: visible;
        }

        .trend-grid {
          stroke: #e9edf2;
          stroke-width: 1;
        }

        .trend-line {
          stroke: #2563eb;
          stroke-width: 3;
          stroke-linecap: round;
          stroke-linejoin: round;
        }

        .trend-point {
          fill: #ffffff;
          stroke: #2563eb;
          stroke-width: 3;
        }

        .trend-label {
          fill: #7b8797;
          font-size: 11px;
        }

        .trend-summary {
          display: flex;
          justify-content: space-between;
          color: #7b8797;
          font-size: 12px;
          padding: 0 5px;
        }

        .trend-summary strong {
          color: #293548;
        }

        .repeat-summary {
          display: grid;
          grid-template-columns:
            repeat(3, minmax(0, 1fr));
          gap: 10px;
          margin-bottom: 20px;
        }

        .repeat-stat {
          padding: 13px;
          background: #f7f9fc;
          border-radius: 10px;
        }

        .repeat-stat-label {
          font-size: 11px;
          color: #7b8797;
        }

        .repeat-stat-value {
          margin-top: 5px;
          font-size: 19px;
          font-weight: 750;
        }

        .repeat-chart {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .repeat-row {
          display: grid;
          grid-template-columns:
            35px
            minmax(80px, 1fr)
            70px;
          align-items: center;
          gap: 10px;
        }

        .repeat-count {
          font-size: 12px;
          font-weight: 700;
        }

        .repeat-fill {
          background: #7c3aed;
        }

        .table-wrapper {
          width: 100%;
          overflow-x: auto;
        }

        .exec-table {
          width: 100%;
          border-collapse: collapse;
          min-width: 800px;
        }

        .exec-table th {
          text-align: left;
          padding: 11px 10px;
          background: #f7f9fc;
          color: #697586;
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
        }

        .exec-table td {
          padding: 12px 10px;
          border-top: 1px solid #edf0f4;
          font-size: 12px;
          color: #394657;
        }

        .exec-table td:not(:first-child) {
          font-weight: 650;
        }

        .heatmap-wrapper {
          width: 100%;
          overflow-x: auto;
        }

        .heatmap-grid {
          display: grid;
          min-width: 720px;
          gap: 3px;
        }

        .heatmap-corner,
        .heatmap-header,
        .heatmap-category,
        .heatmap-cell {
          min-height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 7px;
          border-radius: 5px;
          font-size: 10px;
        }

        .heatmap-corner,
        .heatmap-header {
          background: #eef2f7;
          font-weight: 750;
          color: #4b5869;
        }

        .heatmap-row {
          display: contents;
        }

        .heatmap-category {
          justify-content: flex-start;
          background: #f7f9fc;
          color: #526071;
          font-weight: 650;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .heatmap-cell {
          background: #2563eb;
          color: #ffffff;
          font-weight: 700;
        }

        .empty-state {
          min-height: 150px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #98a2b3;
          font-size: 13px;
        }

        .loading-state {
          min-height: 70vh;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 12px;
          color: #697586;
          font-size: 14px;
        }

        .loading-spinner {
          width: 28px;
          height: 28px;
          border: 3px solid #e3e8ef;
          border-top-color: #2563eb;
          border-radius: 50%;
          animation: exec-spin 0.8s linear infinite;
        }

        @keyframes exec-spin {
          to {
            transform: rotate(360deg);
          }
        }

        .error-box {
          padding: 16px;
          margin-bottom: 18px;
          background: #fff5f5;
          border: 1px solid #ffd6d6;
          color: #b42318;
          border-radius: 10px;
          font-size: 13px;
        }

        @media (max-width: 1100px) {
          .exec-kpi-grid {
            grid-template-columns:
              repeat(2, minmax(0, 1fr));
          }

          .exec-grid-2,
          .exec-grid-3 {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 700px) {
          .executive-dashboard {
            padding: 16px;
          }

          .exec-header {
            flex-direction: column;
          }

          .month-selector {
            width: 100%;
            justify-content: space-between;
          }

          .exec-kpi-grid {
            grid-template-columns: 1fr;
          }

          .bar-row {
            grid-template-columns:
              120px
              minmax(70px, 1fr)
              65px;
          }
        }
      `}</style>

      {/* ====================================================
          HEADER
          ==================================================== */}

      <header className="exec-header">
        <div>
          <h1 className="exec-title">
            Executive Dashboard
          </h1>

          <p className="exec-subtitle">
            Analitik ANEV, PRA, PASCA, klasifikasi
            suspect, dan pola pemeriksaan pelanggan.
          </p>
        </div>

        <div className="month-selector">
          <label htmlFor="executive-month">
            Periode
          </label>

          <select
            id="executive-month"
            value={month}
            onChange={(event) =>
              setMonth(
                event.target.value,
              )
            }
          >
            {months.map(
              (item) => (
                <option
                  key={
                    item.month_key
                  }
                  value={
                    item.month_key
                  }
                >
                  {monthLabel(
                    item,
                  )}
                </option>
              ),
            )}
          </select>
        </div>
      </header>


      {/* ====================================================
          ERROR
          ==================================================== */}

      {error && (
        <div className="error-box">
          {error}
        </div>
      )}


      {/* ====================================================
          LOADING
          ==================================================== */}

      {loading && !data ? (
        <LoadingState />
      ) : (
        <>
          {/* ==================================================
              KPI
              ================================================== */}

          <div className="exec-kpi-grid">
            <KpiCard
              title="Total Lokasi ANEV"
              value={formatNumber(
                pra.total_locations,
              )}
              description={`Periode ${month || "-"}`}
            />

            <KpiCard
              title="Klasifikasi Suspect"
              value={formatNumber(
                pra.total_classifications,
              )}
              description="Klasifikasi aktif pada periode"
            />

            <KpiCard
              title="Lokasi PASCA Berulang"
              value={formatNumber(
                pasca.repeat_locations,
              )}
              description={`Dari ${formatNumber(
                pasca.total_locations,
              )} lokasi cumulative`}
            />

            <KpiCard
              title="Repeat Rate PASCA"
              value={formatPercent(
                pasca.repeat_rate_pct,
              )}
              description={`${formatNumber(
                pasca.repeat_occurrences,
              )} repeat occurrences`}
            />
          </div>


          {/* ==================================================
              TREND + CLASSIFICATION
              ================================================== */}

          <div className="exec-grid-2">
            <Card
              title="Trend Lokasi ANEV"
              subtitle="Jumlah DISTINCT LOCATIONCODE per bulan"
            >
              <TrendChart
                data={trend}
              />
            </Card>

            <Card
              title="Klasifikasi ANEV"
              subtitle="Distribusi lokasi pada periode terpilih"
            >
              <HorizontalBarChart
                data={
                  classification
                }
                height={390}
              />
            </Card>
          </div>


          {/* ==================================================
              UNITAP + ULP + TARIF
              ================================================== */}

          <div className="exec-grid-3">
            <Card
              title="Distribusi UNITAP"
              subtitle="Lokasi ANEV per UNITAP"
            >
              <HorizontalBarChart
                data={unitap}
                height={280}
              />
            </Card>

            <Card
              title="Ranking ULP"
              subtitle="10 ULP dengan lokasi ANEV terbanyak"
            >
              <HorizontalBarChart
                data={ulp}
                height={280}
              />
            </Card>

            <Card
              title="Distribusi Tarif"
              subtitle="Lokasi ANEV berdasarkan tarif"
            >
              <HorizontalBarChart
                data={tariff}
                height={280}
              />
            </Card>
          </div>


          {/* ==================================================
              PRA
              ================================================== */}

          <Card
            title="PRA — Analisis Bulanan"
            subtitle={`Analisis khusus periode ${month || "-"}. PRA tidak menggunakan repeat lintas bulan.`}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "minmax(0, 1.4fr) minmax(0, 1fr)",
                gap: 25,
              }}
            >
              <div>
                <h4
                  style={{
                    margin:
                      "0 0 15px",
                    fontSize: 13,
                  }}
                >
                  Klasifikasi
                </h4>

                <HorizontalBarChart
                  data={
                    pra.classification.map(
                      (item) => ({
                        label:
                          item.classification,
                        value:
                          item.total,
                      }),
                    )
                  }
                  height={360}
                />
              </div>

              <div>
                <h4
                  style={{
                    margin:
                      "0 0 15px",
                    fontSize: 13,
                  }}
                >
                  Distribusi UNITAP
                </h4>

                <VerticalBarChart
                  data={
                    pra.unitap.map(
                      (item) => ({
                        label:
                          item.unitap,
                        value:
                          item.total,
                      }),
                    )
                  }
                />
              </div>
            </div>
          </Card>


          {/* ==================================================
              PASCA REPEAT
              ================================================== */}

          <div
            style={{
              marginTop: 18,
            }}
          >
            <Card
              title="PASCA — Analisis Berulang"
              subtitle="Repeat dihitung berdasarkan kemunculan LOCATIONCODE pada bulan yang berbeda."
            >
              <div className="repeat-summary">
                <div className="repeat-stat">
                  <div className="repeat-stat-label">
                    Total Lokasi
                  </div>

                  <div className="repeat-stat-value">
                    {formatNumber(
                      pasca.total_locations,
                    )}
                  </div>
                </div>

                <div className="repeat-stat">
                  <div className="repeat-stat-label">
                    Lokasi Berulang
                  </div>

                  <div className="repeat-stat-value">
                    {formatNumber(
                      pasca.repeat_locations,
                    )}
                  </div>
                </div>

                <div className="repeat-stat">
                  <div className="repeat-stat-label">
                    Repeat Occurrence
                  </div>

                  <div className="repeat-stat-value">
                    {formatNumber(
                      pasca.repeat_occurrences,
                    )}
                  </div>
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "minmax(0, 1fr) minmax(0, 1.5fr)",
                  gap: 28,
                }}
              >
                <div>
                  <h4
                    style={{
                      margin:
                        "0 0 15px",
                      fontSize: 13,
                    }}
                  >
                    Frekuensi Kemunculan
                  </h4>

                  <RepeatFrequencyChart
                    data={
                      pasca.frequency
                    }
                  />
                </div>

                <div>
                  <h4
                    style={{
                      margin:
                        "0 0 15px",
                      fontSize: 13,
                    }}
                  >
                    Repeat berdasarkan Klasifikasi
                  </h4>

                  <RepeatClassificationTable
                    data={
                      pasca.classification
                    }
                  />
                </div>
              </div>
            </Card>
          </div>


          {/* ==================================================
              HEATMAP
              ================================================== */}

          <div
            style={{
              marginTop: 18,
            }}
          >
            <Card
              title="Heatmap UNITAP × Klasifikasi"
              subtitle="Jumlah DISTINCT LOCATIONCODE pada periode terpilih."
            >
              <Heatmap
                data={heatmap}
              />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}