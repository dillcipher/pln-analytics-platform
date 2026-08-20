from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.constants import RAW_UPLOAD

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


@router.get("/{job_id}")
async def get_job(job_id: str):

    manifest = (
        RAW_UPLOAD
        / job_id
        / "manifest.json"
    )

    if not manifest.exists():
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    with open(
        manifest,
        encoding="utf-8",
    ) as f:

        return json.load(f)