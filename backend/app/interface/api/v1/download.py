from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/download",
    tags=["Download"],
)


@router.get("/{filename}")
async def download(filename: str):

    from app.core.constants import PARQUET

    file = PARQUET / filename

    if not file.exists():

        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return FileResponse(file)