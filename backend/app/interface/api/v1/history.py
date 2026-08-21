from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter

from app.core.constants import RAW_UPLOAD
from app.services.upload_service import (
    S3_BUCKET,
    S3_JOB_PREFIX,
    _create_s3_client,
)


router = APIRouter(
    prefix="/history",
    tags=["History"],
)

RAW_FOLDER = RAW_UPLOAD


async def _read_local_history() -> list[dict]:
    def _read() -> list[dict]:
        jobs: list[dict] = []
        if not RAW_FOLDER.exists():
            return jobs

        for folder in sorted(RAW_FOLDER.iterdir(), reverse=True):
            manifest = folder / "manifest.json"
            if not manifest.exists():
                continue
            try:
                with open(manifest, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    jobs.append(data)
            except (OSError, json.JSONDecodeError):
                continue
        return jobs

    return await asyncio.to_thread(_read)


async def _read_storage_history() -> list[dict]:
    """Read durable job manifests from Supabase Storage.

    Local RAW_UPLOAD is ephemeral on FastAPI Cloud. Supabase Storage is
    therefore the source of truth for upload/ETL history after restarts,
    scale-out, or a new deployment instance.
    """

    def _read() -> list[dict]:
        client = _create_s3_client()
        jobs: list[dict] = []
        seen: set[str] = set()

        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=S3_BUCKET,
            Prefix=f"{S3_JOB_PREFIX}/",
        ):
            for obj in page.get("Contents", []):
                key = str(obj.get("Key", ""))
                if not key.endswith("/manifest.json"):
                    continue

                try:
                    response = client.get_object(
                        Bucket=S3_BUCKET,
                        Key=key,
                    )
                    raw = response["Body"].read()
                    data = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue

                job_id = str(data.get("job_id", ""))
                if job_id and job_id in seen:
                    continue
                if job_id:
                    seen.add(job_id)

                jobs.append(data)

        jobs.sort(
            key=lambda item: str(
                item.get("updated_at")
                or item.get("uploaded_at")
                or item.get("created_at")
                or item.get("job_id", "")
            ),
            reverse=True,
        )
        return jobs

    try:
        return await asyncio.to_thread(_read)
    except Exception:
        # History must remain available locally even when storage is
        # temporarily unavailable.
        return []


@router.get("")
async def get_history():
    """Return durable upload/ETL history across Cloud instances."""
    storage_jobs = await _read_storage_history()
    local_jobs = await _read_local_history()

    merged: dict[str, dict] = {}

    for job in local_jobs + storage_jobs:
        job_id = str(job.get("job_id", "")).strip()
        key = job_id or str(job.get("manifest_path", ""))
        if not key:
            continue
        # Prefer the durable storage copy, which survives instance loss.
        merged[key] = job

    result = list(merged.values())
    result.sort(
        key=lambda item: str(
            item.get("updated_at")
            or item.get("uploaded_at")
            or item.get("created_at")
            or item.get("job_id", "")
        ),
        reverse=True,
    )
    return result
