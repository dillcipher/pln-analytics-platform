from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SuspectMainRow(BaseModel):
    suspect_name: str
    pelanggan: int
    frekuensi: int


class SuspectMainResponse(BaseModel):
    items: list[SuspectMainRow]
    total_rows: int
    page: int
    page_size: int
    total_pages: int


class SuspectSummaryResponse(BaseModel):
    items: list[dict[str, Any]]
    categories: list[str]
    total_rows: int


class SuspectDetailResponse(BaseModel):
    items: list[dict[str, Any]]
    total_rows: int
    page: int
    page_size: int
    total_pages: int


class TrendPoint(BaseModel):
    read_date: str
    value: float


class SuspectDetailTrendResponse(BaseModel):
    location_code: str
    voltage_l1: list[TrendPoint]
    voltage_l2: list[TrendPoint]
    voltage_l3: list[TrendPoint]
    current_l1: list[TrendPoint]
    current_l2: list[TrendPoint]
    current_l3: list[TrendPoint]
    stats: dict[str, float]
