from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.constants import RAW_UPLOAD
from app.infrastructure.storage.processed_storage import persist_processed_data
from app.services.upload_service import UploadService
from app.application.jobs.job_recovery import ensure_job_processing


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


def _read_json_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


async def _get_s3_json(key: str) -> dict | None:
    try:
        if not await UploadService._s3_head(key):
            return None
        data = await UploadService._s3_get_json(key)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _persist_when_finished(data: dict) -> None:
    status = str(data.get("status", "")).upper()
    if status != "FINISHED":
        return
    try:
        await asyncio.to_thread(persist_processed_data)
    except Exception:
        pass


async def _return_job(data: dict, job_id: str) -> dict:
    response = {**data, "success": True, "job_id": job_id}
    await _persist_when_finished(response)
    return response


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get current upload/ETL status and persist finished analytics artifacts."""
    job_id = job_id.strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="Job ID is required.")

    job_folder = RAW_UPLOAD / job_id
    local_manifest = job_folder / "manifest.json"
    local_job_json = job_folder / "job.json"
    local_chunk_metadata = job_folder / "chunk_upload.json"

    try:
        ensure_job_processing(job_id)
    except Exception:
        pass

    local_manifest_data = _read_json_file(local_manifest)
    if local_manifest_data is not None:
        return await _return_job(local_manifest_data, job_id)

    local_job_data = _read_json_file(local_job_json)
    if local_job_data is not None:
        return await _return_job(local_job_data, job_id)

    try:
        manifest_data = await _get_s3_json(
            UploadService._job_manifest_s3_key(job_id),
        )
        if manifest_data is not None:
            return await _return_job(manifest_data, job_id)
    except Exception:
        pass

    try:
        metadata = await _get_s3_json(
            UploadService._job_metadata_s3_key(job_id),
        )
        if metadata is not None:
            return await _return_job(metadata, job_id)
    except Exception:
        pass

    chunk_data = _read_json_file(local_chunk_metadata)
    if chunk_data is not None:
        return await _return_job(chunk_data, job_id)

    raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
