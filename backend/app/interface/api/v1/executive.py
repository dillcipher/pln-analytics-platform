from __future__ import annotations

from fastapi import APIRouter, Query

from app.application.dto.executive_dto import (
    ChartDataResponse,
    KpiResponse,
    MonthOptionResponse,
)
from app.application.use_cases.executive_use_cases import (
    GetExecutiveCharts,
    GetExecutiveKpis,
    GetExecutiveMonths,
)


router = APIRouter(
    prefix="/executive",
    tags=["Executive"],
)


# ==========================================================
# MONTHS
# ==========================================================


@router.get("/months")
def get_months() -> dict:
    """
    Return available months for Executive Dashboard.
    """

    months = GetExecutiveMonths().execute()

    data = [
        MonthOptionResponse(
            month_key=month.month_key,
            label=month.label,
        )
        for month in months
    ]

    return {
        "success": True,
        "count": len(data),
        "data": data,
    }


# ==========================================================
# KPI
# ==========================================================


@router.get("/kpis")
def get_kpis(
    month: str | None = Query(
        None,
        description="Executive month key, for example 202606.",
    ),
) -> dict:
    """
    Return Executive Dashboard KPI for the selected month.

    If month is omitted, the latest available month is used.
    """

    data = GetExecutiveKpis().execute(
        month_key=month,
    )

    return {
        "success": True,
        "data": KpiResponse(**data),
    }


# ==========================================================
# CHARTS
# ==========================================================


@router.get("/charts")
def get_charts(
    month: str | None = Query(
        None,
        description="Executive month key, for example 202606.",
    ),
) -> dict:
    """
    Return the complete Executive Dashboard payload.

    The repository is responsible for calculating the analytical
    values. The API layer only validates and serializes the contract.

    This is intentionally simpler than manually splitting
    data_science from the legacy chart payload: ChartDataResponse
    already contains the complete nested DataScienceResponse.
    """

    data = GetExecutiveCharts().execute(
        month_key=month,
    )

    chart_data = ChartDataResponse(**data)

    if hasattr(chart_data, "model_dump"):
        response_data = chart_data.model_dump()
    else:
        response_data = chart_data.dict()

    return {
        "success": True,
        "data": response_data,
    }
