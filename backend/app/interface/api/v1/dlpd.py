from __future__ import annotations

from typing import Any, Literal

import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from fastapi.responses import StreamingResponse

from app.application.dto.dlpd_dto import (
    DlpdCustomerDetailResponse,
    DlpdCustomerListResponse,
    DlpdDashboardResponse,
    DlpdDashboardUlpResponse,
    DlpdFilterOptionsResponse,
)

from app.application.dto.executive_dto import (
    MonthOptionResponse,
)

from app.application.use_cases.dlpd_use_cases import (
    ExportDlpdCustomers,
    GetDlpdCustomerDetail,
    GetDlpdCustomers,
    GetDlpdDashboard,
    GetDlpdDashboardUlp,
    GetDlpdFilterOptions,
    GetDlpdMapPoints,
    GetDlpdMonths,
)

from app.core.config import get_settings

from app.domain.repositories import (
    DlpdFilters,
)

from app.infrastructure.auth.user_store import (
    AuthenticatedUser,
)

from app.infrastructure.duckdb.dlpd_repository import (
    DuckDbDlpdRepository,
)

from app.interface.api.deps import (
    get_current_user,
    get_dlpd_repository,
)

from app.interface.api.export_utils import (
    build_export_filename,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(__name__)


# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(
    prefix="/dlpd",
    tags=["dlpd-monitoring"],
)


CustomerType = Literal[
    "prabayar",
    "pascabayar",
]


# ==========================================================
# COMMON
# ==========================================================

def _clean(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    value = value.strip()

    return value or None


def _normalize_month(
    value: str | None,
) -> str | None:
    """
    Normalize the month query parameter before it reaches the
    application/use-case/repository layer.

    Contract:
    - None / empty            -> all months
    - __ALL_MONTHS__          -> all months
    - ALL / ALL_MONTHS       -> all months
    - all months / semua     -> all months
    - YYYYMM                  -> YYYYMM
    - YYYY-MM / YYYY/MM      -> YYYYMM

    The frontend uses an explicit ALL_MONTHS sentinel for its
    "Semua Bulan" mode. The backend must translate that sentinel
    to None instead of treating it as a real month key.
    """

    value = _clean(value)

    if value is None:
        return None

    normalized = value.strip().lower()

    all_month_values = {
        "__all_months__",
        "__all_month__",
        "all",
        "all_months",
        "all_month",
        "all-months",
        "all-month",
        "all months",
        "all month",
        "semua",
        "semua_bulan",
        "semua_bulan_",
        "semua bulan",
        "semua bulan",
    }

    if normalized in all_month_values:
        return None

    compact = (
        normalized
        .replace("-", "")
        .replace("/", "")
        .replace(" ", "")
    )

    if compact.isdigit() and len(compact) == 6:
        return compact

    # Keep the original cleaned value for backwards compatibility.
    # The repository/use-case remains responsible for rejecting or
    # returning empty data for an invalid concrete month key.
    return value


def _normalize_idpel(value: str) -> str:
    """Normalize IDPEL received from a URL before querying the backend."""
    cleaned = str(value or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IDPEL tidak boleh kosong.",
        )

    # Excel/DuckDB exports sometimes expose numeric IDPEL values as 123456.0.
    if cleaned.endswith(".0") and cleaned[:-2].isdigit():
        cleaned = cleaned[:-2]

    return cleaned


def _google_maps_url(
    *,
    latitude: float | int | None = None,
    longitude: float | int | None = None,
    address: str | None = None,
    idpel: str | None = None,
) -> str:
    """Build a Google Maps URL without requiring Google Maps API access.

    Coordinates are preferred because they point directly to the customer
    location. Address/IDPEL are used as a fallback when coordinates are not
    available.
    """
    from urllib.parse import quote_plus

    if latitude is not None and longitude is not None:
        try:
            lat = float(latitude)
            lon = float(longitude)
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (
                    "https://www.google.com/maps/search/?api=1"
                    f"&query={lat},{lon}"
                )
        except (TypeError, ValueError):
            pass

    parts = [
        str(address).strip() if address else "",
        f"IDPEL {str(idpel).strip()}" if idpel else "",
    ]
    query = ", ".join(part for part in parts if part)

    if not query:
        return "https://www.google.com/maps"

    return (
        "https://www.google.com/maps/search/?api=1"
        f"&query={quote_plus(query)}"
    )


def _backend_error(
    operation: str,
    exc: Exception,
) -> HTTPException:
    """Convert an internal DLPD failure into a useful API error."""
    logger.exception("DLPD %s failed", operation)

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            f"Gagal memuat {operation}. "
            "Periksa backend dan dataset DLPD."
        ),
    )


def _build_filters(
    unitupi: str | None,
    unitap: str | None,
    unitup: str | None,
    tariff: str | None,
    status: str | None,
    inspection_status: str | None,
    dlpd_repeat: str | None,
    kendala: str | None,
    search_idpel: str | None,
    search_nama: str | None,
) -> DlpdFilters:

    return DlpdFilters(
        unitupi=_clean(unitupi),
        unitap=_clean(unitap),
        unitup=_clean(unitup),
        tariff=_clean(tariff),

        # ==================================================
        # STATUS HASIL
        # NORMAL / TEMUAN
        # ==================================================

        status=_clean(status),

        # ==================================================
        # STATUS PEMERIKSAAN
        # SUDAH PERIKSA / BELUM PERIKSA
        # ==================================================

        inspection_status=_clean(
            inspection_status,
        ),

        dlpd_repeat=_clean(
            dlpd_repeat,
        ),

        kendala=_clean(
            kendala,
        ),

        search_idpel=_clean(
            search_idpel,
        ),

        search_nama=_clean(
            search_nama,
        ),
    )


# ==========================================================
# MONTH
# ==========================================================

@router.get(
    "/months",
    response_model=list[MonthOptionResponse],
)
def get_months(

    customer_type: CustomerType = Query(
        "prabayar",
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> list[MonthOptionResponse]:

    try:
        months = GetDlpdMonths(
            repo,
        ).execute(
            customer_type,
        )
    except Exception as exc:
        raise _backend_error("daftar bulan", exc) from exc

    return [
        MonthOptionResponse(
            month_key=m.month_key,
            label=m.label,
        )
        for m in months
    ]


# ==========================================================
# FILTER
# ==========================================================

@router.get(
    "/filters",
    response_model=DlpdFilterOptionsResponse,
)
def get_filters(

    customer_type: CustomerType = Query(
        "prabayar",
    ),

    month: str | None = Query(
        None,
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> DlpdFilterOptionsResponse:

    try:
        options = GetDlpdFilterOptions(
            repo,
        ).execute(
            customer_type,
            _normalize_month(month),
        )
    except Exception as exc:
        raise _backend_error("filter DLPD", exc) from exc

    return DlpdFilterOptionsResponse(
        **options,
    )


# ==========================================================
# DASHBOARD KPI
# ==========================================================

@router.get(
    "/dashboard",
    response_model=DlpdDashboardResponse,
)
def get_dashboard(

    customer_type: CustomerType = Query(
        "prabayar",
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

    status: str | None = Query(
        None,
    ),

    inspection_status: str | None = Query(
        None,
    ),

    dlpd_repeat: str | None = Query(
        None,
    ),

    kendala: str | None = Query(
        None,
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> DlpdDashboardResponse:

    filters = _build_filters(
        unitupi,
        unitap,
        unitup,
        tariff,
        status,
        inspection_status,
        dlpd_repeat,
        kendala,
        None,
        None,
    )

    try:
        result = GetDlpdDashboard(
            repo,
        ).execute(
            customer_type,
            _normalize_month(month),
            filters,
        )
    except Exception as exc:
        raise _backend_error("KPI DLPD", exc) from exc

    return DlpdDashboardResponse.model_validate(
        result,
    )


# ==========================================================
# DASHBOARD ULP
# ==========================================================

@router.get(
    "/dashboard-ulp",
    response_model=list[DlpdDashboardUlpResponse],
)
def get_dashboard_ulp(

    customer_type: CustomerType = Query(
        "prabayar",
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

    status: str | None = Query(
        None,
    ),

    inspection_status: str | None = Query(
        None,
    ),

    dlpd_repeat: str | None = Query(
        None,
    ),

    kendala: str | None = Query(
        None,
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> list[DlpdDashboardUlpResponse]:

    filters = _build_filters(
        unitupi,
        unitap,
        unitup,
        tariff,
        status,
        inspection_status,
        dlpd_repeat,
        kendala,
        None,
        None,
    )

    try:
        result = GetDlpdDashboardUlp(
            repo,
        ).execute(
            customer_type,
            _normalize_month(month),
            filters,
        )
    except Exception as exc:
        raise _backend_error("dashboard ULP", exc) from exc

    # Always return a list. This keeps the frontend contract stable even when
    # the selected month/unit has no matching ULP rows.
    if result is None:
        return []

    return [
        DlpdDashboardUlpResponse.model_validate(row)
        for row in result
    ]


# ==========================================================
# MAP POINTS
# ==========================================================

@router.get(
    "/map",
)
def get_map_points(

    customer_type: CustomerType = Query(
        "prabayar",
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

    status: str | None = Query(
        None,
    ),

    inspection_status: str | None = Query(
        None,
    ),

    dlpd_repeat: str | None = Query(
        None,
    ),

    kendala: str | None = Query(
        None,
    ),

    search_idpel: str | None = Query(
        None,
    ),

    search_nama: str | None = Query(
        None,
    ),

    # ======================================================
    # MAP LIMIT
    #
    # Frontend dapat meminta sampai 100.000 point.
    # Repository juga akan menjaga batas maksimalnya.
    # ======================================================

    limit: int = Query(
        100_000,
        ge=1,
        le=100_000,
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> dict:

    filters = _build_filters(
        unitupi,
        unitap,
        unitup,
        tariff,
        status,
        inspection_status,
        dlpd_repeat,
        kendala,
        search_idpel,
        search_nama,
    )

    try:
        result = GetDlpdMapPoints(
            repo,
        ).execute(
            customer_type=customer_type,
            month_key=_normalize_month(month),
            filters=filters,
            limit=limit,
        )
    except Exception as exc:
        raise _backend_error("data peta", exc) from exc

    return result


# ==========================================================
# CUSTOMER LIST
# ==========================================================

@router.get(
    "/customers",
    response_model=DlpdCustomerListResponse,
)
def get_customers(

    customer_type: CustomerType = Query(
        "prabayar",
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

    status: str | None = Query(
        None,
    ),

    inspection_status: str | None = Query(
        None,
    ),

    dlpd_repeat: str | None = Query(
        None,
    ),

    kendala: str | None = Query(
        None,
    ),

    search_idpel: str | None = Query(
        None,
    ),

    search_nama: str | None = Query(
        None,
    ),

    page: int = Query(
        1,
        ge=1,
    ),

    page_size: int | None = Query(
        None,
        ge=1,
        le=1000,
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> DlpdCustomerListResponse:

    settings = get_settings()

    filters = _build_filters(
        unitupi,
        unitap,
        unitup,
        tariff,
        status,
        inspection_status,
        dlpd_repeat,
        kendala,
        search_idpel,
        search_nama,
    )

    try:
        result = GetDlpdCustomers(
            repo,
        ).execute(
            customer_type,
            _normalize_month(month),
            filters,
            page,
            page_size or settings.DEFAULT_PAGE_SIZE,
        )
    except Exception as exc:
        raise _backend_error("daftar pelanggan", exc) from exc

    return DlpdCustomerListResponse(
        items=result.items,
        total_rows=result.total_rows,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


# ==========================================================
# CUSTOMER DETAIL
# ==========================================================

@router.get(
    "/customers/{idpel}",
    response_model=DlpdCustomerDetailResponse,
)
def get_customer_detail(

    idpel: str,

    month: str | None = Query(
        None,
    ),

    customer_type: CustomerType = Query(
        "prabayar",
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

) -> DlpdCustomerDetailResponse:

    normalized_idpel = _normalize_idpel(idpel)

    try:
        result = GetDlpdCustomerDetail(
            repo,
        ).execute(
            customer_type,
            normalized_idpel,
            _normalize_month(month),
        )
    except Exception as exc:
        raise _backend_error("detail pelanggan", exc) from exc

    if result is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return DlpdCustomerDetailResponse.model_validate(
        result,
    )


# ==========================================================
# CUSTOMER -> GOOGLE MAPS
# ==========================================================

@router.get(
    "/customers/{idpel}/maps",
)
def get_customer_google_maps(
    idpel: str,
    month: str | None = Query(
        None,
    ),
    customer_type: CustomerType = Query(
        "prabayar",
    ),
    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),
    _: AuthenticatedUser = Depends(
        get_current_user,
    ),
) -> dict[str, Any]:
    """Return a direct Google Maps URL for the selected customer.

    The frontend can open ``google_maps_url`` in a new tab/window when the
    user clicks the Google Maps button in the Detail Pelanggan panel.
    """
    normalized_idpel = _normalize_idpel(idpel)

    try:
        result = GetDlpdCustomerDetail(
            repo,
        ).execute(
            customer_type,
            normalized_idpel,
            _normalize_month(month),
        )
    except Exception as exc:
        raise _backend_error("lokasi pelanggan", exc) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # ``result`` is normally a DlpdCustomerDetail domain object. Keep this
    # endpoint defensive so it works with either a domain object or a dict.
    customer = getattr(result, "customer", None)

    if customer is None and isinstance(result, dict):
        customer = result.get("customer", result)

    def value(name: str, default: Any = None) -> Any:
        if customer is None:
            return default
        if isinstance(customer, dict):
            return customer.get(name, default)
        return getattr(customer, name, default)

    latitude = value("latitude")
    longitude = value("longitude")
    address = value("alamat") or value("address")

    url = _google_maps_url(
        latitude=latitude,
        longitude=longitude,
        address=address,
        idpel=normalized_idpel,
    )

    return {
        "idpel": normalized_idpel,
        "latitude": latitude,
        "longitude": longitude,
        "alamat": address,
        "google_maps_url": url,
    }


# ==========================================================
# EXPORT
# ==========================================================

@router.get(
    "/customers/export/{fmt}",
)
def export_customers(

    fmt: str,

    customer_type: CustomerType = Query(
        "prabayar",
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

    status: str | None = Query(
        None,
    ),

    inspection_status: str | None = Query(
        None,
    ),

    dlpd_repeat: str | None = Query(
        None,
    ),

    kendala: str | None = Query(
        None,
    ),

    search_idpel: str | None = Query(
        None,
    ),

    search_nama: str | None = Query(
        None,
    ),

    repo: DuckDbDlpdRepository = Depends(
        get_dlpd_repository,
    ),

    _: AuthenticatedUser = Depends(
        get_current_user,
    ),

):

    fmt = fmt.lower().strip()

    if fmt not in (
        "csv",
        "xlsx",
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'csv' or 'xlsx'.",
        )

    filters = _build_filters(
        unitupi,
        unitap,
        unitup,
        tariff,
        status,
        inspection_status,
        dlpd_repeat,
        kendala,
        search_idpel,
        search_nama,
    )

    try:
        rows = ExportDlpdCustomers(
            repo,
        ).execute(
            customer_type,
            _normalize_month(month),
            filters,
        )
    except Exception as exc:
        raise _backend_error("export pelanggan", exc) from exc

    filename = build_export_filename(
        f"dlpd_{customer_type}",
        _normalize_month(month),
        fmt,
    )

    if fmt == "csv":

        content = rows_to_csv_bytes(
            rows,
        )

        media_type = "text/csv"

    else:

        content = rows_to_xlsx_bytes(
            rows,
            f"DLPD {customer_type.title()}",
        )

        media_type = (
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        )

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        },
    )