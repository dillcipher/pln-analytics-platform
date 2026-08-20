from __future__ import annotations

from pydantic import BaseModel, Field


# ==========================================================
# MONTH
# ==========================================================


class MonthOptionResponse(BaseModel):
    month_key: str
    label: str


# ==========================================================
# KPI
# ==========================================================


class KpiResponse(BaseModel):
    month_key: str | None

    total_customers: int

    total_suspects: int

    total_normal: int

    total_findings: int

    remaining_inspection: int

    progress_pct: float

    hit_rate_pct: float


# ==========================================================
# GENERIC CHART
# ==========================================================


class ChartSeriesPoint(BaseModel):
    label: str
    value: float


# ==========================================================
# HEATMAP
# ==========================================================


class HeatmapPoint(BaseModel):
    unitap: str
    category: str
    value: float


# ==========================================================
# ANEV CLASSIFICATION
# ==========================================================


class AnevClassificationPoint(BaseModel):
    label: str
    value: float


# ==========================================================
# ANEV UNITAP / TARIFF
# ==========================================================


class AnevUnitapPoint(BaseModel):
    label: str
    value: float


class AnevTariffPoint(BaseModel):
    label: str
    value: float


# ==========================================================
# PRA MONTHLY
# ==========================================================


class PraClassificationPoint(BaseModel):
    classification: str
    total: int


class PraUnitapPoint(BaseModel):
    unitap: str
    total: int


class PraMonthlyResponse(BaseModel):
    total_locations: int
    total_classifications: int

    classification: list[PraClassificationPoint] = Field(
        default_factory=list,
    )

    unitap: list[PraUnitapPoint] = Field(
        default_factory=list,
    )


# ==========================================================
# PASCA REPEAT FREQUENCY
# ==========================================================


class PascaRepeatFrequencyPoint(BaseModel):
    repeat_count: int
    locations: int


# ==========================================================
# PASCA REPEAT BY CLASSIFICATION
# ==========================================================


class PascaRepeatClassificationPoint(BaseModel):
    classification: str

    total_locations: int

    repeat_locations: int

    repeat_occurrences: int


# ==========================================================
# PASCA REPEAT SUMMARY
# ==========================================================


class PascaRepeatResponse(BaseModel):
    total_locations: int

    repeat_locations: int

    repeat_occurrences: int

    repeat_rate_pct: float

    frequency: list[PascaRepeatFrequencyPoint] = Field(
        default_factory=list,
    )

    classification: list[PascaRepeatClassificationPoint] = Field(
        default_factory=list,
    )


# ==========================================================
# COMPATIBILITY REPEAT CASE
# ==========================================================


class RepeatCasePoint(BaseModel):
    label: str
    value: float


# ==========================================================
# ANALYTICAL EVIDENCE
# ==========================================================


class PriorityByClassificationPoint(BaseModel):
    """
    Classification priority score calculated by the repository.

    priority_score combines PRA exposure, PASCA exposure,
    and repeat/persistence according to the repository
    analytical layer.
    """

    classification: str

    pra_total: int

    pasca_total: int

    repeat_locations: int

    repeat_occurrences: int

    priority_score: float


class PriorityByUnitapPoint(BaseModel):
    """
    UNITAP priority score calculated by the repository.

    priority_score combines current PRA exposure and
    repeat intensity.
    """

    unitap: str

    pra_locations: int

    pasca_locations: int

    repeat_locations: int

    repeat_occurrences: int

    repeat_rate_pct: float

    priority_score: float


class InspectionCoverageResponse(BaseModel):
    """
    Inspection coverage for the selected Executive period.
    """

    total_population: int

    inspected: int

    remaining: int

    normal: int

    findings: int

    coverage_pct: float

    finding_rate_pct: float


class RepeatIntensityResponse(BaseModel):
    """
    PASCA persistence intensity for the selected period/window.
    """

    total_locations: int

    repeat_locations: int

    repeat_occurrences: int

    repeat_rate_pct: float

    avg_repeat_occurrences_per_repeat_location: float

    max_repeat_count: int


class ConcentrationUnitapPoint(BaseModel):
    unitap: str

    locations: int

    share_pct: float


class ConcentrationResponse(BaseModel):
    """
    Distribution/concentration of suspect locations by UNITAP.
    """

    unitap: list[ConcentrationUnitapPoint] = Field(
        default_factory=list,
    )

    top_unitap: ConcentrationUnitapPoint | None = None

    top_3_share_pct: float = 0.0


# ==========================================================
# DATA SCIENCE / STATISTICAL EVIDENCE
# ==========================================================


class CorrelationPoint(BaseModel):
    """
    Pearson correlation between two numeric variables.

    The repository must provide this from an actual statistical
    calculation. The application layer does not fabricate it.
    """

    feature_x: str

    feature_y: str

    correlation: float

    abs_correlation: float

    p_value: float | None = None

    sample_size: int | None = None

    significant: bool | None = None


class LinearRegressionPoint(BaseModel):
    """
    Simple linear regression result:

        target = intercept + slope * feature
    """

    feature: str

    target: str

    slope: float

    intercept: float

    r_squared: float

    sample_size: int

    p_value: float | None = None

    significant: bool | None = None


class FeatureImportancePoint(BaseModel):
    """
    Feature importance / model contribution ranking.

    These values are optional because the current analytical
    repository may intentionally keep ML/statistical model
    outputs empty until a real model is available.
    """

    feature: str

    target: str

    importance: float

    direction: str | None = None

    correlation: float | None = None


class PraPascaClassificationPoint(BaseModel):
    """
    Suspect classification by customer type.

    customer_type:
        PRA / PASCA

    classification:
        Suspect classification label.
    """

    customer_type: str

    classification: str

    total: int


class DataScienceResponse(BaseModel):
    """
    Complete analytical payload for Executive.

    Statistical/model outputs remain empty when the repository
    does not have a real statistical/model result.

    Descriptive analytical evidence may be populated independently.

    Nested analytical summaries are optional because they may not
    be available for every period. The API must not fail merely
    because one analytical extension has no result.
    """

    # ======================================================
    # STATISTICAL / MODEL OUTPUT
    # ======================================================

    correlation: list[CorrelationPoint] = Field(
        default_factory=list,
    )

    linear_regression: list[LinearRegressionPoint] = Field(
        default_factory=list,
    )

    feature_importance: list[FeatureImportancePoint] = Field(
        default_factory=list,
    )

    pra_pasca_classification: list[
        PraPascaClassificationPoint
    ] = Field(
        default_factory=list,
    )

    # ======================================================
    # ANALYTICAL EVIDENCE
    # ======================================================

    priority_by_unitap: list[PriorityByUnitapPoint] = Field(
        default_factory=list,
    )

    priority_by_classification: list[
        PriorityByClassificationPoint
    ] = Field(
        default_factory=list,
    )

    # ------------------------------------------------------
    # IMPORTANT:
    #
    # These are optional.
    #
    # Do NOT use:
    #
    #     default_factory=InspectionCoverageResponse
    #
    # because InspectionCoverageResponse contains required
    # fields and cannot be constructed without actual data.
    # ------------------------------------------------------

    inspection_coverage: InspectionCoverageResponse | None = None

    repeat_intensity: RepeatIntensityResponse | None = None

    concentration: ConcentrationResponse | None = None


# ==========================================================
# CHART DATA
# ==========================================================


class ChartDataResponse(BaseModel):
    """
    Complete Executive Dashboard chart payload.

    Contains:

        Existing Executive charts
        ANEV charts
        PRA monthly analytics
        PASCA repeat analytics
        Analytical Evidence
        Optional statistical/model evidence
    """

    # ======================================================
    # EXISTING EXECUTIVE CHARTS
    # ======================================================

    bar_by_unitap: list[ChartSeriesPoint] = Field(
        default_factory=list,
    )

    pie_by_tariff: list[ChartSeriesPoint] = Field(
        default_factory=list,
    )

    donut_by_segment: list[ChartSeriesPoint] = Field(
        default_factory=list,
    )

    monthly_trend: list[ChartSeriesPoint] = Field(
        default_factory=list,
    )

    ranking_by_ulp: list[ChartSeriesPoint] = Field(
        default_factory=list,
    )

    heatmap_unitap_x_category: list[HeatmapPoint] = Field(
        default_factory=list,
    )

    # ======================================================
    # ANEV
    # ======================================================

    anev_classification: list[AnevClassificationPoint] = Field(
        default_factory=list,
    )

    anev_by_unitap: list[AnevUnitapPoint] = Field(
        default_factory=list,
    )

    anev_by_tariff: list[AnevTariffPoint] = Field(
        default_factory=list,
    )

    # ======================================================
    # PRA
    # ======================================================

    pra_monthly: PraMonthlyResponse = Field(
        default_factory=PraMonthlyResponse,
    )

    # ======================================================
    # PASCA
    # ======================================================

    pasca_repeat: PascaRepeatResponse = Field(
        default_factory=PascaRepeatResponse,
    )

    # ======================================================
    # ANALYTICAL EVIDENCE / DATA SCIENCE
    # ======================================================

    data_science: DataScienceResponse = Field(
        default_factory=DataScienceResponse,
    )

    # ======================================================
    # COMPATIBILITY
    # ======================================================

    repeat_cases: list[RepeatCasePoint] = Field(
        default_factory=list,
    )