from __future__ import annotations

from fastapi import APIRouter

from app.database.warehouse import Warehouse

router = APIRouter(
    prefix="/warehouse",
    tags=["Warehouse"],
)


@router.post("/refresh")
def refresh():

    Warehouse.refresh_tables()

    return {
        "success": True,
        "message": "Warehouse refreshed successfully.",
    }