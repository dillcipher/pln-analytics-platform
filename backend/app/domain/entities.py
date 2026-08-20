"""
Domain entities: plain dataclasses with zero framework dependencies
(no Pydantic, no FastAPI, no DuckDB).

These describe the business concepts the platform reasons about;
the `application` layer orchestrates them and the `interface`
layer translates them to/from HTTP.

DLPD location metadata is intentionally kept inside the customer
payload (`DlpdCustomerDetail.customer`) because Google Maps URLs and
coordinate fields are transport/presentation metadata, not separate
business objects in the current domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# =====================================================
# COMMON
# =====================================================


@dataclass(frozen=True)
class MonthOption:
    """One selectable entry in a Month dropdown."""

    month_key: str
    label: str


@dataclass(frozen=True)
class PageResult:
    """Generic paginated result envelope."""

    items: list[dict]
    total_rows: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 1

        return max(
            1,
            -(
                -self.total_rows
                // self.page_size
            ),
        )


# =====================================================
# EXECUTIVE
# =====================================================


@dataclass(frozen=True)
class KpiSet:
    """
    Executive Dashboard KPI for one month.
    """

    month_key: str

    total_customers: int

    total_suspects: int

    total_normal: int

    total_findings: int

    remaining_inspection: int

    progress_pct: float

    hit_rate_pct: float


@dataclass(frozen=True)
class ExecutiveChartItem:
    """
    Generic item used by Executive Dashboard charts.

    Example:

        label = "17174"
        value = 12345
    """

    label: str
    value: int


@dataclass(frozen=True)
class ExecutiveTrendItem:
    """
    One point in a monthly Executive Dashboard trend.
    """

    label: str
    value: float


@dataclass(frozen=True)
class ExecutiveHeatmapItem:
    """
    One cell in the Executive UNITAP x classification heatmap.
    """

    unitap: str
    category: str
    value: int


@dataclass(frozen=True)
class ExecutiveRepeatItem:
    """
    Repeat information for one suspect classification.
    """

    classification: str

    total_customers: int

    repeat_customers: int

    repeat_occurrences: int


@dataclass(frozen=True)
class ExecutiveRepeatSummary:
    """
    Overall repeat analysis for the selected Executive month.
    """

    total_customers: int

    repeat_customers: int

    repeat_occurrences: int

    repeat_rate_pct: float

    by_suspect: list[ExecutiveRepeatItem] = field(
        default_factory=list,
    )


@dataclass(frozen=True)
class ExecutiveChartData:
    """
    Complete Executive Dashboard chart payload.

    The repository may still return dictionaries internally,
    but this entity documents the business structure expected
    by the application layer.
    """

    bar_by_unitap: list[ExecutiveChartItem] = field(
        default_factory=list,
    )

    pie_by_tariff: list[ExecutiveChartItem] = field(
        default_factory=list,
    )

    donut_by_segment: list[ExecutiveChartItem] = field(
        default_factory=list,
    )

    monthly_trend: list[ExecutiveTrendItem] = field(
        default_factory=list,
    )

    ranking_by_ulp: list[ExecutiveChartItem] = field(
        default_factory=list,
    )

    heatmap_unitap_x_category: list[
        ExecutiveHeatmapItem
    ] = field(
        default_factory=list,
    )

    repeat_cases: ExecutiveRepeatSummary | None = None


# =====================================================
# DLPD
# =====================================================


@dataclass(frozen=True)
class DlpdDashboard:
    total_target: int

    normal: int

    temuan: int

    belum_periksa: int

    @property
    def sudah_periksa(self) -> int:
        return max(
            self.normal + self.temuan,
            0,
        )

    @property
    def progress_pct(self) -> float:
        if self.total_target <= 0:
            return 0.0

        return round(
            self.sudah_periksa
            / self.total_target
            * 100,
            2,
        )


@dataclass(frozen=True)
class DlpdDashboardUlp:
    """
    Summary of one ULP in the DLPD dashboard.

    `kwh_lt40` and `kwh_zero` are populated only for
    Pascabayar; they remain None for Prabayar.
    """

    unitup: str

    unit_name: str

    total: int

    normal: int

    temuan: int

    belum_periksa: int

    # khusus Pascabayar
    kwh_lt40: int | None = None

    kwh_zero: int | None = None

    @property
    def total_pemeriksaan(self) -> int:
        return max(
            self.normal + self.temuan,
            0,
        )

    @property
    def percentage(self) -> float:
        if self.total <= 0:
            return 0.0

        return round(
            self.total_pemeriksaan
            / self.total
            * 100,
            2,
        )


@dataclass(frozen=True)
class InspectionHistory:
    """
    One historical inspection record for a DLPD customer.
    """

    waktu_periksa: Any | None = None

    status: str | None = None

    petugas: str | None = None

    regu: str | None = None

    catatan: str | None = None

    tindak_lanjut: str | None = None


@dataclass(frozen=True)
class DlpdCustomerDetail:
    """
    Complete customer detail payload.

    The `customer` dictionary may contain the normal customer fields
    plus optional location metadata supplied by the repository:

        latitude
        longitude
        coordinate_source
        google_maps_url

    Keeping these values in the existing dictionary preserves the
    current domain contract while allowing the Detail Pelanggan UI
    to open Google Maps directly.
    """

    customer: dict[str, Any]

    inspection_history: list[
        InspectionHistory
    ] = field(
        default_factory=list,
    )
