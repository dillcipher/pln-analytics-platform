from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from fastapi.responses import Response

from app.application.use_cases.data_management_use_cases import (
    ExportDataManagement,
    GetDataManagementCatalog,
    GetDataManagementFilterOptions,
    GetDataManagementOverview,
    GetDataManagementStatus,
    PreviewDataManagement,
)


router = APIRouter(
    prefix="/data-management",
    tags=["Data Management"],
)


# ==========================================================
# OVERVIEW
# ==========================================================

@router.get(
    "/overview",
)
def overview():
    """
    Return Data Management overview.

    Used by the Data Management frontend
    for KPI cards and dataset registry.
    """

    try:
        data = (
            GetDataManagementOverview()
            .execute()
        )

        return {
            "success": True,
            "data": data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# CATALOG
# ==========================================================

@router.get(
    "/catalog",
)
def catalog():

    try:

        data = (
            GetDataManagementCatalog()
            .execute()
        )

        return {
            "success": True,
            "data": data,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# STATUS
# ==========================================================

@router.get(
    "/status",
)
def status():

    try:

        data = (
            GetDataManagementStatus()
            .execute()
        )

        return {
            "success": True,
            "data": data,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# FILTER OPTIONS
# ==========================================================

@router.get(
    "/filters",
)
def filters(
    dataset: str = Query(
        ...,
        description=(
            "Data Management dataset key."
        ),
    ),
    month: str | None = Query(
        None,
        description=(
            "Optional month filter."
        ),
    ),
):

    try:

        data = (
            GetDataManagementFilterOptions()
            .execute(
                dataset,
                month,
            )
        )

        return {
            "success": True,
            "data": data,
        }

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail=(
                "Dataset export tidak dikenal"
            ),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# PREVIEW
# ==========================================================

@router.get(
    "/preview",
)
def preview(
    dataset: str = Query(
        ...,
        description=(
            "Data Management dataset key."
        ),
    ),
    month: str | None = Query(
        None,
    ),
    unitupi: str | None = Query(
        None,
    ),
    unitap: str | None = Query(
        None,
    ),
    unitup: str | None = Query(
        None,
    ),
    tariff: str | None = Query(
        None,
    ),
    segment: str | None = Query(
        None,
    ),
    suspect_name: str | None = Query(
        None,
    ),
    location_code: str | None = Query(
        None,
    ),
    idpel: str | None = Query(
        None,
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
):

    filters_payload = {
        "month": month,
        "unitupi": unitupi,
        "unitap": unitap,
        "unitup": unitup,
        "tariff": tariff,
        "segment": segment,
        "suspect_name": suspect_name,
        "location_code": location_code,
        "idpel": idpel,
    }

    try:

        data = (
            PreviewDataManagement()
            .execute(
                dataset,
                month,
                filters_payload,
                limit,
            )
        )

        return {
            "success": True,
            "data": data,
        }

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail=(
                "Dataset export tidak dikenal"
            ),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# EXPORT
# ==========================================================

@router.get(
    "/export",
)
def export(
    dataset: str = Query(
        ...,
        description=(
            "Data Management dataset key."
        ),
    ),
    month: str | None = Query(
        None,
    ),
    unitupi: str | None = Query(
        None,
    ),
    unitap: str | None = Query(
        None,
    ),
    unitup: str | None = Query(
        None,
    ),
    tariff: str | None = Query(
        None,
    ),
    segment: str | None = Query(
        None,
    ),
    suspect_name: str | None = Query(
        None,
    ),
    location_code: str | None = Query(
        None,
    ),
    idpel: str | None = Query(
        None,
    ),
    columns: str | None = Query(
        None,
        description=(
            "Comma-separated export columns."
        ),
    ),
):

    filters_payload = {
        "month": month,
        "unitupi": unitupi,
        "unitap": unitap,
        "unitup": unitup,
        "tariff": tariff,
        "segment": segment,
        "suspect_name": suspect_name,
        "location_code": location_code,
        "idpel": idpel,
    }

    try:

        selected_columns = (
            [
                value.strip()
                for value
                in columns.split(",")
                if value.strip()
            ]
            if columns
            else None
        )

        data, filename = (
            ExportDataManagement()
            .execute(
                dataset,
                month,
                filters_payload,
                selected_columns,
            )
        )

        return Response(
            content=data,
            media_type=(
                "text/csv; charset=utf-8"
            ),
            headers={
                "Content-Disposition": (
                    'attachment; '
                    f'filename="{filename}"'
                ),
                "Cache-Control": "no-store",
            },
        )

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail=(
                "Dataset export tidak dikenal"
            ),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )