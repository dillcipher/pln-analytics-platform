from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService


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

    Important:

        manifest.json represents the assembled job.

        job.json represents the durable job state and can exist
        before assembly finishes.

    This endpoint must therefore continue returning a job while
    assembly or ETL is running instead of returning 404 merely
    because manifest.json is not available yet.
    """

    # ==========================================================
    # VALIDATE JOB ID
    # ==========================================================

    job_id = job_id.strip()

    if not job_id:
        raise HTTPException(
            status_code=400,
            detail="Job ID is required.",
        )

    # ==========================================================
    # PATHS
    # ==========================================================

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

    # ==========================================================
    # 1. LOCAL MANIFEST
    #
    # Fast path.
    #
    # This is preferred because the current worker may be
    # actively updating the manifest while ETL is running.
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
    #
    # IMPORTANT:
    #
    # Do this BEFORE going to Supabase.
    #
    # A background worker may already have created/updated
    # job.json locally while manifest.json has not been created
    # yet.
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
    #
    # Durable state after assembly.
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
    #
    # This should exist immediately after upload/complete.
    #
    # It is especially important during:
    #
    #     ASSEMBLY_QUEUED
    #     ASSEMBLING
    #     ASSEMBLY_FAILED
    #
    # when manifest.json may not exist yet.
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
    #
    # Last local fallback.
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

    # ==========================================================
    # JOB DOES NOT EXIST
    # ==========================================================

    raise HTTPException(
        status_code=404,
        detail=f"Job not found: {job_id}",
    )