from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ==========================================================
# FILTER
# ==========================================================


class DlpdFilterOptionsResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    months: list[str]

    unitupi: list[str]

    unitap: list[str]

    unitup: list[str]

    # Status hasil pemeriksaan:
    # NORMAL / TEMUAN
    status: list[str]

    # Status pemeriksaan:
    # SUDAH PERIKSA / BELUM PERIKSA
    inspection_status: list[str]

    dlpd_repeat: list[str]

    kendala: list[str]


# ==========================================================
# DASHBOARD KPI
# ==========================================================


class DlpdDashboardResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    total_target: int

    normal: int

    temuan: int

    belum_periksa: int

    sudah_periksa: int

    progress_pct: float


# ==========================================================
# DASHBOARD ULP
# ==========================================================


class DlpdDashboardUlpResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    unitup: str

    unit_name: str

    total: int

    normal: int

    temuan: int

    belum_periksa: int

    total_pemeriksaan: int

    percentage: float

    # Khusus Pascabayar
    kwh_lt40: int | None = None

    kwh_zero: int | None = None


# ==========================================================
# CUSTOMER LIST
# ==========================================================


class DlpdCustomerResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    idpel: str

    nama: str

    unitupi: str | None = None

    unitap: str | None = None

    unitup: str | None = None

    tariff: str | None = None

    daya: int | None = None

    alamat: str | None = None

    status: str

    dlpd_repeat: str | None = None

    kategori: str | None = None

    keterangan: str | None = None

    alasan: str | None = None

    catatan: str | None = None

    petugas: str | None = None

    regu: str | None = None

    waktu_periksa: datetime | None = None

    # Optional location fields.
    # These remain optional so the existing customer-list contract
    # stays compatible while the repository is being upgraded to
    # expose customer coordinates.
    latitude: float | None = None

    longitude: float | None = None

    google_maps_url: str | None = None


class DlpdCustomerListResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    items: list[DlpdCustomerResponse]

    total_rows: int

    page: int

    page_size: int

    total_pages: int


# ==========================================================
# CUSTOMER DETAIL
# ==========================================================


class InspectionHistoryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    waktu_periksa: datetime | None = None

    status: str | None = None

    petugas: str | None = None

    regu: str | None = None

    catatan: str | None = None

    tindak_lanjut: str | None = None


class DlpdCustomerDetailResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    customer: dict[str, Any] | None

    inspection_history: list[
        InspectionHistoryResponse
    ]

    # Optional top-level location metadata.
    # The current domain object may not populate these yet, so they
    # deliberately remain optional and do not break model validation.
    latitude: float | None = None

    longitude: float | None = None

    google_maps_url: str | None = None
