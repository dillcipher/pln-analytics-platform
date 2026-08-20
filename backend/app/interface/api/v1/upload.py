from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.core.constants import RAW_UPLOAD
from app.schemas.upload_schema import UploadResponse
from app.services.upload_service import UploadService


router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


# ==========================================================
# BACKGROUND ETL
# ==========================================================


def _run_etl(
    job_folder: Path,
) -> None:
    """
    Run ETL after a job has been completely assembled.

    IMPORTANT:
    This function is ONLY for ETL.

    Chunk assembly is NOT performed here.
    """

    try:
        print("=" * 80)
        print("BACKGROUND ETL START")
        print(f"JOB FOLDER : {job_folder}")
        print("=" * 80)

        if not job_folder.exists():
            raise FileNotFoundError(
                f"Job folder not found: {job_folder}"
            )

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found: {manifest_path}"
            )

        print(
            f"✓ Manifest found: {manifest_path}"
        )

        ETLOrchestrator.process(
            job_folder,
        )

        print("=" * 80)
        print("BACKGROUND ETL FINISHED")
        print(f"JOB FOLDER : {job_folder}")
        print("=" * 80)

    except Exception:
        print("=" * 80)
        print("BACKGROUND ETL FAILED")
        print(f"JOB FOLDER : {job_folder}")
        print("=" * 80)

        traceback.print_exc()


# ==========================================================
# NORMAL SMALL FILE UPLOAD
# ==========================================================


@router.post(
    "/files",
    response_model=UploadResponse,
)
async def upload_files(
    background_tasks: BackgroundTasks,
    file: Annotated[
        UploadFile,
        File(
            ...,
            description="Excel file to upload",
        ),
    ],
):
    start = time.perf_counter()

    print("=" * 80)
    print("UPLOAD API CALLED")
    print("UPLOAD MODE : NORMAL")
    print("TOTAL FILES : 1")
    print(f"FILE        : {file.filename}")
    print("=" * 80)

    try:
        result = await UploadService.save_files(
            [file],
        )

        job_folder = (
            RAW_UPLOAD
            / result["job_id"]
        )

        # Normal/small uploads can use background ETL.
        background_tasks.add_task(
            _run_etl,
            job_folder,
        )

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print(
            f"UPLOAD FINISHED ({duration:.2f}s)"
        )
        print(
            "ETL RUNNING IN BACKGROUND..."
        )
        print(
            f"JOB ID : {result['job_id']}"
        )
        print("=" * 80)

        return result

    except Exception as e:
        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print("UPLOAD FAILED")
        print(f"ERROR    : {e}")
        print(f"DURATION : {duration:.2f}s")
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ==========================================================
# CHUNK UPLOAD
#
# One request = one chunk.
#
# Example:
#
# chunk 0 -> 20 MB
# chunk 1 -> 20 MB
# chunk 2 -> 20 MB
# ...
#
# This prevents Cloudflare from receiving the entire
# 700+ MB Excel file in a single HTTP request.
# ==========================================================


@router.post(
    "/chunk",
)
async def upload_chunk(
    upload_id: Annotated[
        str,
        Form(
            ...,
            description="Unique upload ID",
        ),
    ],
    filename: Annotated[
        str,
        Form(
            ...,
            description="Original filename",
        ),
    ],
    chunk_number: Annotated[
        int,
        Form(
            ...,
            ge=0,
            description="Zero-based chunk number",
        ),
    ],
    total_chunks: Annotated[
        int,
        Form(
            ...,
            gt=0,
            description="Total number of chunks",
        ),
    ],
    file: Annotated[
        UploadFile,
        File(
            ...,
            description="One upload chunk",
        ),
    ],
):
    start = time.perf_counter()

    print("=" * 80)
    print("CHUNK UPLOAD")
    print(f"UPLOAD ID    : {upload_id}")
    print(f"FILE         : {filename}")
    print(
        f"CHUNK        : "
        f"{chunk_number + 1}/{total_chunks}"
    )
    print("=" * 80)

    try:
        result = await UploadService.save_chunk(
            upload_id=upload_id,
            filename=filename,
            chunk_number=chunk_number,
            total_chunks=total_chunks,
            file=file,
        )

        duration = (
            time.perf_counter()
            - start
        )

        print(
            f"CHUNK FINISHED ({duration:.2f}s)"
        )

        return result

    except ValueError as e:
        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ==========================================================
# COMPLETE CHUNKED UPLOAD
#
# IMPORTANT:
#
# /complete DOES NOT return immediately anymore.
#
# It performs:
#
#   1. Verify all chunks
#   2. Create job
#   3. Assemble the complete XLSX
#   4. Detect dataset
#   5. Resolve month
#   6. Create manifest.json
#   7. Verify manifest.json
#   8. Return job_id
#
# ETL IS NOT STARTED HERE.
#
# This is intentional.
#
# The caller must use:
#
#   POST /api/v1/upload/process/{job_id}
#
# after /complete returns successfully.
# ==========================================================


@router.post(
    "/complete",
    response_model=UploadResponse,
)
async def complete_upload(
    upload_id: Annotated[
        str,
        Form(
            ...,
            description="Unique upload ID",
        ),
    ],
    filename: Annotated[
        str,
        Form(
            ...,
            description="Original filename",
        ),
    ],
    total_chunks: Annotated[
        int,
        Form(
            ...,
            gt=0,
            description="Total number of chunks",
        ),
    ],
    content_type: Annotated[
        str | None,
        Form(
            description="Original file content type",
        ),
    ] = None,
):
    start = time.perf_counter()

    print("=" * 80)
    print("COMPLETE CHUNKED UPLOAD")
    print(f"UPLOAD ID    : {upload_id}")
    print(f"FILE         : {filename}")
    print(f"TOTAL CHUNKS : {total_chunks}")
    print("=" * 80)

    try:
        # ======================================================
        # STEP 1
        # VERIFY CHUNKS + CREATE JOB
        # ======================================================

        prepared = await UploadService.prepare_chunk_upload(
            upload_id=upload_id,
            filename=filename,
            total_chunks=total_chunks,
            content_type=content_type,
        )

        job_id = prepared["job_id"]

        job_folder = (
            RAW_UPLOAD
            / job_id
        )

        print("=" * 80)
        print("CHUNK UPLOAD PREPARED")
        print(f"UPLOAD ID : {upload_id}")
        print(f"JOB ID    : {job_id}")
        print(f"JOB FOLDER: {job_folder}")
        print("=" * 80)

        # ======================================================
        # STEP 2
        # ASSEMBLE SYNCHRONOUSLY
        #
        # DO NOT use BackgroundTasks here.
        #
        # We must guarantee that when /complete returns 200:
        #
        #   final XLSX exists
        #   manifest.json exists
        #
        # This prevents the previous failure where:
        #
        # /complete → 200
        # deployment restart
        # background assembly/ETL disappears
        # ======================================================

        result = await UploadService.assemble_chunk_upload(
            upload_id=upload_id,
            job_id=job_id,
            filename=filename,
            total_chunks=total_chunks,
            content_type=content_type,
        )

        # ======================================================
        # STEP 3
        # VERIFY FINAL JOB
        # ======================================================

        final_job_folder = (
            RAW_UPLOAD
            / result["job_id"]
        )

        if not final_job_folder.exists():
            raise FileNotFoundError(
                f"Job folder not found after assembly: "
                f"{final_job_folder}"
            )

        manifest_path = (
            final_job_folder
            / "manifest.json"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found after assembly: "
                f"{manifest_path}"
            )

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print("CHUNKED UPLOAD COMPLETED")
        print(f"JOB ID       : {result['job_id']}")
        print(f"MANIFEST     : {manifest_path}")
        print(f"DURATION     : {duration:.2f}s")
        print("ASSEMBLY     : COMPLETED")
        print("MANIFEST     : READY")
        print("ETL          : NOT STARTED")
        print("=" * 80)

        return result

    except FileNotFoundError as e:
        traceback.print_exc()

        raise HTTPException(
            status_code=404,
            detail=str(e),
        )

    except ValueError as e:
        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print("COMPLETE UPLOAD FAILED")
        print(f"ERROR    : {e}")
        print(f"DURATION : {duration:.2f}s")
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ==========================================================
# PROCESS EXISTING JOB
#
# Endpoint:
#
# POST /api/v1/upload/process/{job_id}
#
# This endpoint ONLY starts ETL.
#
# It requires:
#
#   job folder exists
#   manifest.json exists
#
# Therefore /complete must succeed first.
# ==========================================================


@router.post(
    "/process/{job_id}",
)
async def process_existing_job(
    job_id: str,
    background_tasks: BackgroundTasks,
):
    start = time.perf_counter()

    print("=" * 80)
    print("PROCESS EXISTING JOB")
    print(f"JOB ID : {job_id}")
    print("=" * 80)

    job_folder = (
        RAW_UPLOAD
        / job_id
    )

    # ======================================================
    # VERIFY JOB
    # ======================================================

    if not job_folder.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}",
        )

    manifest_path = (
        job_folder
        / "manifest.json"
    )

    if not manifest_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Manifest not found for job: "
                f"{job_id}"
            ),
        )

    # ======================================================
    # START ETL
    # ======================================================

    background_tasks.add_task(
        _run_etl,
        job_folder,
    )

    duration = (
        time.perf_counter()
        - start
    )

    print("=" * 80)
    print("ETL SCHEDULED")
    print(f"JOB ID   : {job_id}")
    print(f"DURATION : {duration:.2f}s")
    print("=" * 80)

    return {
        "success": True,
        "job_id": job_id,
        "message": "ETL scheduled",
    }