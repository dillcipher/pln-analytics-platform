from __future__ import annotations

import asyncio
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
# ETL
# ==========================================================

def _run_etl(
    job_folder: Path,
) -> None:

    try:
        print("=" * 80)
        print("BACKGROUND ETL START")
        print("JOB FOLDER :", job_folder)
        print("=" * 80)

        if not job_folder.exists():
            raise FileNotFoundError(
                f"Job folder not found: {job_folder}",
            )

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found: {manifest_path}",
            )

        print(
            "✓ Manifest found:",
            manifest_path,
        )

        print("=" * 80)
        print("RUNNING ETL ORCHESTRATOR")
        print("JOB FOLDER :", job_folder)
        print("=" * 80)

        ETLOrchestrator.process(
            job_folder,
        )

        print("=" * 80)
        print("BACKGROUND ETL FINISHED")
        print("JOB FOLDER :", job_folder)
        print("=" * 80)

    except Exception:
        print("=" * 80)
        print("BACKGROUND ETL FAILED")
        print("JOB FOLDER :", job_folder)
        print("=" * 80)

        traceback.print_exc()


# ==========================================================
# ASSEMBLY + ETL
#
# IMPORTANT:
#
# This entire heavy operation runs AFTER /complete has
# already returned.
#
# Therefore Cloudflare does NOT wait for the large assembly.
# ==========================================================

async def _run_assembly_and_etl(
    upload_id: str,
    job_id: str,
    filename: str,
    total_chunks: int,
    content_type: str | None,
) -> None:

    job_folder = (
        RAW_UPLOAD
        / job_id
    )

    try:
        print("=" * 80)
        print("BACKGROUND ASSEMBLY + ETL START")
        print("UPLOAD ID :", upload_id)
        print("JOB ID    :", job_id)
        print("FILE      :", filename)
        print("=" * 80)

        # --------------------------------------------------
        # ASSEMBLY
        # --------------------------------------------------

        result = (
            await UploadService.assemble_chunk_upload(
                upload_id=upload_id,
                job_id=job_id,
                filename=filename,
                total_chunks=total_chunks,
                content_type=content_type,
            )
        )

        print("=" * 80)
        print("ASSEMBLY RESULT")
        print(result)
        print("=" * 80)

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found after assembly: "
                f"{manifest_path}",
            )

        print("=" * 80)
        print("ASSEMBLY COMPLETED")
        print("JOB ID   :", job_id)
        print("MANIFEST :", manifest_path)
        print("=" * 80)

        # --------------------------------------------------
        # ETL
        #
        # ETL starts ONLY after manifest exists.
        # --------------------------------------------------

        print("=" * 80)
        print("STARTING ETL")
        print("JOB ID :", job_id)
        print("=" * 80)

        await asyncio.to_thread(
            _run_etl,
            job_folder,
        )

        print("=" * 80)
        print("ASSEMBLY + ETL PIPELINE FINISHED")
        print("JOB ID :", job_id)
        print("=" * 80)

    except Exception:
        print("=" * 80)
        print("ASSEMBLY + ETL FAILED")
        print("JOB ID :", job_id)
        print("=" * 80)

        traceback.print_exc()


# ==========================================================
# NORMAL SMALL UPLOAD
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

    try:
        result = await UploadService.save_files(
            [file],
        )

        job_folder = (
            RAW_UPLOAD
            / result["job_id"]
        )

        background_tasks.add_task(
            _run_etl,
            job_folder,
        )

        duration = (
            time.perf_counter()
            - start
        )

        print(
            f"UPLOAD FINISHED ({duration:.2f}s)",
        )

        return result

    except Exception as exc:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# CHUNK
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

    try:
        return await UploadService.save_chunk(
            upload_id=upload_id,
            filename=filename,
            chunk_number=chunk_number,
            total_chunks=total_chunks,
            file=file,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# COMPLETE CHUNKED UPLOAD
#
# THIS MUST BE FAST.
#
# It does NOT assemble the large file inside the request.
#
# It only:
#
#   1. verify chunks
#   2. create job
#   3. queue background assembly
#   4. return job_id
#
# Cloudflare therefore does not wait for assembly.
# ==========================================================

@router.post(
    "/complete",
    response_model=UploadResponse,
)
async def complete_upload(
    background_tasks: BackgroundTasks,
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
    print("UPLOAD ID    :", upload_id)
    print("FILE         :", filename)
    print("TOTAL CHUNKS :", total_chunks)
    print("=" * 80)

    try:
        # --------------------------------------------------
        # ONLY VERIFY + CREATE JOB
        # --------------------------------------------------

        result = (
            await UploadService.prepare_chunk_upload(
                upload_id=upload_id,
                filename=filename,
                total_chunks=total_chunks,
                content_type=content_type,
            )
        )

        job_id = result["job_id"]

        # --------------------------------------------------
        # QUEUE HEAVY WORK
        # --------------------------------------------------

        background_tasks.add_task(
            _run_assembly_and_etl,
            upload_id,
            job_id,
            filename,
            total_chunks,
            content_type,
        )

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print("CHUNKED UPLOAD ACCEPTED")
        print("JOB ID   :", job_id)
        print("ASSEMBLY : RUNNING IN BACKGROUND")
        print(
            f"DURATION : {duration:.2f}s",
        )
        print("=" * 80)

        return {
            **result,
            "status": "ASSEMBLY_QUEUED",
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# PROCESS EXISTING JOB
#
# Manual ETL trigger.
# ==========================================================

@router.post(
    "/process/{job_id}",
)
async def process_existing_job(
    job_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger ETL for an existing job.

    The job may have been created by a previous application instance.
    Local RAW_UPLOAD storage is therefore treated as a cache, not the
    source of truth.

    Recovery order:

        1. Local manifest -> schedule ETL immediately.
        2. Durable Supabase job metadata -> recover the assembled file
           from Supabase when local storage is missing/incomplete.
        3. After recovery creates manifest.json -> schedule ETL.

    This prevents a valid durable job from returning 404 merely because
    the FastAPI instance was restarted or replaced.
    """

    start = time.perf_counter()

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

    manifest_path = (
        job_folder
        / "manifest.json"
    )

    # ==========================================================
    # FAST PATH: LOCAL MANIFEST ALREADY EXISTS
    # ==========================================================

    if manifest_path.exists():

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
        print("JOB ID   :", job_id)
        print("SOURCE   : LOCAL MANIFEST")
        print(
            f"DURATION : {duration:.2f}s",
        )
        print("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "status": "ETL_QUEUED",
            "message": "ETL scheduled",
        }

    # ==========================================================
    # DURABLE RECOVERY
    #
    # Local storage may disappear when the FastAPI instance is
    # restarted/replaced. Job metadata and the final assembled
    # Excel are persisted in Supabase.
    # ==========================================================

    try:
        metadata_key = (
            UploadService._job_metadata_s3_key(
                job_id,
            )
        )

        metadata_exists = await UploadService._s3_head(
            metadata_key,
        )

        if not metadata_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}",
            )

        metadata = await UploadService._s3_get_json(
            metadata_key,
        )

        if not isinstance(metadata, dict):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Durable metadata not found for job: "
                    f"{job_id}"
                ),
            )

        filename = (
            metadata.get("filename")
            or metadata.get("original_filename")
        )

        if not filename:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Job metadata has no filename: "
                    f"{job_id}"
                ),
            )

        content_type = metadata.get(
            "content_type",
        )

        print("=" * 80)
        print("RECOVERING DURABLE JOB")
        print("JOB ID   :", job_id)
        print("FILENAME :", filename)
        print("SOURCE   : SUPABASE")
        print("=" * 80)

        # recover_assembled_job is deliberately used here instead
        # of assemble_chunk_upload().
        #
        # The former first checks for the durable FINAL FILE and
        # downloads it when local storage is gone. This is important
        # because successful assembly deletes the original chunks
        # from Supabase.
        await UploadService.recover_assembled_job(
            job_id=job_id,
            filename=filename,
            content_type=content_type,
        )

        # ======================================================
        # VERIFY RECOVERY
        # ======================================================

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest was not created during recovery: "
                f"{manifest_path}"
            )

        background_tasks.add_task(
            _run_etl,
            job_folder,
        )

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print("DURABLE JOB RECOVERED")
        print("JOB ID   :", job_id)
        print("MANIFEST :", manifest_path)
        print("ETL      : SCHEDULED")
        print(
            f"DURATION : {duration:.2f}s",
        )
        print("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "status": "ETL_QUEUED",
            "message": (
                "Job recovered from durable storage; "
                "ETL scheduled"
            ),
        }

    except HTTPException:
        raise

    except FileNotFoundError as exc:
        # The durable metadata exists, but the assembled final file
        # is not available yet. That means assembly is still running
        # (or the durable upload is incomplete), not that the job ID
        # itself is invalid.
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job is not ready for ETL yet: "
                f"{job_id}. "
                f"{exc}"
            ),
        )

    except Exception as exc:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to recover/process job "
                f"{job_id}: {exc}"
            ),
        )


# ==========================================================
# RECOVER ALREADY-ASSEMBLED JOB
#
# This endpoint is specifically for a job where the
# assembled file and/or manifest already exist.
#
# IMPORTANT:
#
# An existing manifest does NOT mean that ETL finished.
#
# Therefore:
#
#   manifest exists
#        ↓
#   schedule ETL
#
# instead of simply returning "Manifest already exists".
# ==========================================================

@router.post(
    "/recover/{job_id}",
)
async def recover_existing_job(
    job_id: str,
    filename: Annotated[
        str,
        Form(
            ...,
            description="Assembled filename",
        ),
    ],
    content_type: Annotated[
        str | None,
        Form(
            description="Original content type",
        ),
    ] = None,
    background_tasks: BackgroundTasks = None,
):

    job_folder = (
        RAW_UPLOAD
        / job_id
    )

    if not job_folder.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}",
        )

    manifest_path = (
        job_folder
        / "manifest.json"
    )

    # ======================================================
    # MANIFEST ALREADY EXISTS
    #
    # IMPORTANT:
    #
    # Manifest existence only proves that assembly metadata
    # was persisted.
    #
    # It does NOT prove that ETL completed successfully.
    #
    # Therefore always continue to ETL.
    # ======================================================

    if manifest_path.exists():

        print("=" * 80)
        print("RECOVER EXISTING JOB")
        print("JOB ID :", job_id)
        print("MANIFEST :", manifest_path)
        print("STATUS : MANIFEST EXISTS")
        print("ACTION : SCHEDULE ETL")
        print("=" * 80)

        if background_tasks is not None:
            background_tasks.add_task(
                _run_etl,
                job_folder,
            )

        return {
            "success": True,
            "job_id": job_id,
            "status": "ETL_QUEUED",
            "message": (
                "Manifest exists; ETL scheduled"
            ),
        }

    # ======================================================
    # MANIFEST DOES NOT EXIST
    #
    # Recover the already-assembled local file first.
    # ======================================================

    try:

        print("=" * 80)
        print("RECOVER ASSEMBLED JOB")
        print("JOB ID  :", job_id)
        print("FILE    :", filename)
        print("=" * 80)

        result = (
            await UploadService.recover_assembled_job(
                job_id=job_id,
                filename=filename,
                content_type=content_type,
            )
        )

        # --------------------------------------------------
        # VERIFY MANIFEST
        # --------------------------------------------------

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest was not created during recovery: "
                f"{manifest_path}",
            )

        print("=" * 80)
        print("RECOVERY COMPLETED")
        print("JOB ID   :", job_id)
        print("MANIFEST :", manifest_path)
        print("ACTION   : SCHEDULE ETL")
        print("=" * 80)

        # --------------------------------------------------
        # START ETL
        # --------------------------------------------------

        if background_tasks is not None:
            background_tasks.add_task(
                _run_etl,
                job_folder,
            )

        return {
            **result,
            "status": "ETL_QUEUED",
            "message": (
                "Recovered and ETL scheduled"
            ),
        }

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )