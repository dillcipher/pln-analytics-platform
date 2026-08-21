from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService
from app.interface.api.v1.upload import ensure_job_processing


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


def _read_json_file(
    path: Path,
) -> dict | None:
    """
    Safely read a local JSON file.

    Returns:
        dict | None
    """

    if not path.exists():
        return None

    try:
        with open(
            path,
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except (
        OSError,
        json.JSONDecodeError,
    ):
        pass

    return None


async def _get_s3_json(
    key: str,
) -> dict | None:
    """
    Safely read a JSON object from durable Supabase/S3 storage.

    Returns:
        dict | None
    """

    try:
        exists = await UploadService._s3_head(
            key,
        )

        if not exists:
            return None

        data = await UploadService._s3_get_json(
            key,
        )

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return None


@router.get("/{job_id}")
async def get_job(
    job_id: str,
):
    """
    Get the current status of an upload/ETL job.

    Source priority:

        1. Local manifest.json
        2. Local job.json
        3. Supabase manifest.json
        4. Supabase job.json
        5. Local chunk_upload.json

    The endpoint also acts as the durable-job wake-up mechanism.
    The frontend already polls this endpoint, so every poll is allowed
    to idempotently kick an unfinished durable job after a FastAPI Cloud
    instance restart. The upload router prevents duplicate in-process
    execution for the same job_id.
    """

    job_id = job_id.strip()

    if not job_id:
        raise HTTPException(
            status_code=400,
            detail="Job ID is required.",
        )

    job_folder = (
        RAW_UPLOAD
        / job_id
    )

    local_manifest = (
        job_folder
        / "manifest.json"
    )

    local_job_json = (
        job_folder
        / "job.json"
    )

    local_chunk_metadata = (
        job_folder
        / "chunk_upload.json"
    )

    # ----------------------------------------------------------
    # DURABLE WAKE-UP
    # ----------------------------------------------------------
    #
    # This is intentionally fire-and-forget. It does not block the
    # status response on assembly or ETL. If the current instance was
    # restarted, the in-memory task registry is empty and this poll
    # becomes the automatic resume trigger.
    #
    try:
        ensure_job_processing(job_id)
    except Exception:
        # Status reporting must remain available even if the wake-up
        # mechanism encounters an unexpected scheduling error.
        pass

    # ==========================================================
    # 1. LOCAL MANIFEST
    # ==========================================================

    local_manifest_data = _read_json_file(
        local_manifest,
    )

    if local_manifest_data is not None:
        return {
            **local_manifest_data,
            "success": True,
            "job_id": job_id,
        }

    # ==========================================================
    # 2. LOCAL JOB METADATA
    # ==========================================================

    local_job_data = _read_json_file(
        local_job_json,
    )

    if local_job_data is not None:
        return {
            **local_job_data,
            "success": True,
            "job_id": job_id,
        }

    # ==========================================================
    # 3. SUPABASE MANIFEST
    # ==========================================================

    try:
        manifest_key = (
            UploadService._job_manifest_s3_key(
                job_id,
            )
        )

        manifest_data = await _get_s3_json(
            manifest_key,
        )

        if manifest_data is not None:
            return {
                **manifest_data,
                "success": True,
                "job_id": job_id,
            }

    except Exception:
        pass

    # ==========================================================
    # 4. SUPABASE JOB METADATA
    # ==========================================================

    try:
        metadata_key = (
            UploadService._job_metadata_s3_key(
                job_id,
            )
        )

        metadata = await _get_s3_json(
            metadata_key,
        )

        if metadata is not None:
            return {
                **metadata,
                "success": True,
                "job_id": job_id,
            }

    except Exception:
        pass

    # ==========================================================
    # 5. LOCAL CHUNK METADATA
    # ==========================================================

    chunk_data = _read_json_file(
        local_chunk_metadata,
    )

    if chunk_data is not None:
        return {
            **chunk_data,
            "success": True,
            "job_id": job_id,
        }

    raise HTTPException(
        status_code=404,
        detail=f"Job not found: {job_id}",
    )
