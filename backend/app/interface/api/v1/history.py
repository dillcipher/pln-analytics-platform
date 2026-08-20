from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(
    prefix="/history",
    tags=["History"],
)

from app.core.constants import RAW_UPLOAD

RAW_FOLDER = RAW_UPLOAD


@router.get("")
async def get_history():

    jobs = []

    if not RAW_FOLDER.exists():
        return []

    for folder in sorted(
        RAW_FOLDER.iterdir(),
        reverse=True,
    ):

        manifest = folder / "manifest.json"

        if not manifest.exists():
            continue

        with open(
            manifest,
            encoding="utf-8",
        ) as f:

            jobs.append(json.load(f))

    return jobs