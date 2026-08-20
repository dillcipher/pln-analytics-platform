import api from "./api";


// ==========================================================
// MONTH
// ==========================================================

export interface ExecutiveMonth {
    month_key: string;
    label: string;
}


// ==========================================================
// KPI
// ==========================================================

export interface ExecutiveKpi {
    month_key: string | null;
    total_customers: number;
    total_suspects: number;
    total_normal: number;
    total_findings: number;
    remaining_inspection: number;
    progress_pct: number;
    hit_rate_pct: number;
}


// ==========================================================
// GENERIC CHART
// ==========================================================

export interface ChartSeriesPoint {
    label: string;
    value: number;
}


// ==========================================================
// HEATMAP
// ==========================================================

export interface HeatmapPoint {
    unitap: string;
    category: string;
    value: number;
}


// ==========================================================
// ANEV
// ==========================================================

export interface AnevClassificationPoint {
    label: string;
    value: number;
}

export interface AnevUnitapPoint {
    label: string;
    value: number;
}

export interface AnevTariffPoint {
    label: string;
    value: number;
}


// ==========================================================
// PRA
// ==========================================================

export interface PraClassificationPoint {
    classification: string;
    total: number;
}

export interface PraUnitapPoint {
    unitap: string;
    total: number;
}

export interface PraMonthly {
    total_locations: number;
    total_classifications: number;
    classification: PraClassificationPoint[];
    unitap: PraUnitapPoint[];
}


// ==========================================================
// PASCA
// ==========================================================

export interface PascaRepeatFrequencyPoint {
    repeat_count: number;
    locations: number;
}

export interface PascaRepeatClassificationPoint {
    classification: string;
    total_locations: number;
    repeat_locations: number;
    repeat_occurrences: number;
}

export interface PascaRepeat {
    total_locations: number;
    repeat_locations: number;
    repeat_occurrences: number;
    repeat_rate_pct: number;
    frequency: PascaRepeatFrequencyPoint[];
    classification: PascaRepeatClassificationPoint[];
}


// ==========================================================
// COMPATIBILITY
// ==========================================================

export interface RepeatCasePoint {
    label: string;
    value: number;
}


// ==========================================================
// STATISTICAL / MODEL EVIDENCE
// ==========================================================

export interface CorrelationPoint {
    feature_x: string;
    feature_y: string;
    correlation: number;
    abs_correlation: number;
}

export interface LinearRegressionPoint {
    feature: string;
    target: string;
    slope: number;
    intercept: number;
    r_squared: number;
    sample_size: number;
    p_value?: number | null;
}

export interface FeatureImportancePoint {
    feature: string;
    target: string;
    importance: number;
    direction?: string | null;
    correlation?: number | null;
}

export interface PraPascaClassificationPoint {
    customer_type: string;
    classification: string;
    total: number;
}


// ==========================================================
// ANALYTICAL EVIDENCE
// ==========================================================

export interface PriorityByClassificationPoint {
    classification: string;
    pra_total: number;
    pasca_total: number;
    repeat_locations: number;
    repeat_occurrences: number;
    priority_score: number;
}

export interface PriorityByUnitapPoint {
    unitap: string;
    pra_locations: number;
    pasca_locations: number;
    repeat_locations: number;
    repeat_occurrences: number;
    repeat_rate_pct: number;
    priority_score: number;
}

export interface InspectionCoverage {
    total_population: number;
    inspected: number;
    remaining: number;
    normal: number;
    findings: number;
    coverage_pct: number;
    finding_rate_pct: number;
}

export interface RepeatIntensity {
    total_locations: number;
    repeat_locations: number;
    repeat_occurrences: number;
    repeat_rate_pct: number;
    avg_repeat_occurrences_per_repeat_location: number;
    max_repeat_count: number;
}

export interface ConcentrationUnitapPoint {
    unitap: string;
    locations: number;
    share_pct: number;
}

export interface Concentration {
    unitap: ConcentrationUnitapPoint[];
    top_unitap: ConcentrationUnitapPoint | null;
    top_3_share_pct: number;
}


// ==========================================================
// COMPLETE ANALYTICAL PAYLOAD
// ==========================================================

export interface ExecutiveDataScience {
    // Kept for compatibility with genuine statistical/model
    // outputs. Current repository intentionally leaves these
    // empty until real models are available.
    correlation: CorrelationPoint[];
    linear_regression: LinearRegressionPoint[];
    feature_importance: FeatureImportancePoint[];

    pra_pasca_classification: PraPascaClassificationPoint[];

    priority_by_unitap: PriorityByUnitapPoint[];
    priority_by_classification: PriorityByClassificationPoint[];

    inspection_coverage: InspectionCoverage;
    repeat_intensity: RepeatIntensity;
    concentration: Concentration;
}


// ==========================================================
// COMPLETE CHART RESPONSE
// ==========================================================

export interface ExecutiveCharts {
    bar_by_unitap: ChartSeriesPoint[];
    pie_by_tariff: ChartSeriesPoint[];
    donut_by_segment: ChartSeriesPoint[];
    monthly_trend: ChartSeriesPoint[];
    ranking_by_ulp: ChartSeriesPoint[];
    heatmap_unitap_x_category: HeatmapPoint[];

    anev_classification: AnevClassificationPoint[];
    anev_by_unitap: AnevUnitapPoint[];
    anev_by_tariff: AnevTariffPoint[];

    pra_monthly: PraMonthly;

    pasca_repeat: PascaRepeat;

    data_science: ExecutiveDataScience;

    repeat_cases: RepeatCasePoint[];
}


// ==========================================================
// API RESPONSE ENVELOPES
// ==========================================================

export interface ExecutiveMonthsResponse {
    success: boolean;
    count: number;
    data: ExecutiveMonth[];
}

export interface ExecutiveKpiResponse {
    success: boolean;
    data: ExecutiveKpi;
}

export interface ExecutiveChartsResponse {
    success: boolean;
    data: ExecutiveCharts;
}


// ==========================================================
// HELPERS
// ==========================================================

function normalizeMonth(month: string | null | undefined): string | undefined {
    const value = String(month ?? "").trim();
    return value || undefined;
}


// ==========================================================
// MONTHS
// ==========================================================

export async function getExecutiveMonths(): Promise<ExecutiveMonth[]> {
    const response = await api.get<ExecutiveMonthsResponse>(
        "/executive/months",
    );

    return Array.isArray(response.data?.data)
        ? response.data.data
        : [];
}


// ==========================================================
// KPI
// ==========================================================

export async function getExecutiveKpis(
    monthKey?: string | null,
): Promise<ExecutiveKpi> {
    const month = normalizeMonth(monthKey);

    const response = await api.get<ExecutiveKpiResponse>(
        "/executive/kpis",
        {
            params: month ? { month } : undefined,
        },
    );

    return response.data.data;
}


// ==========================================================
// CHARTS
// ==========================================================

export async function getExecutiveCharts(
    monthKey?: string | null,
): Promise<ExecutiveCharts> {
    const month = normalizeMonth(monthKey);

    const response = await api.get<ExecutiveChartsResponse>(
        "/executive/charts",
        {
            params: month ? { month } : undefined,
        },
    );

    return response.data.data;
}
