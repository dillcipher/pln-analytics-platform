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
    Run ETL for a completed upload.

    IMPORTANT:
    This function is intentionally isolated from the chunk
    assembly itself. Assembly must finish first and create
    manifest.json before ETL starts.
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
# NORMAL UPLOAD
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

        # Normal/small uploads can continue through
        # the existing background ETL mechanism.
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
# Chunk assembly is the only operation performed here.
#
# The completed file and manifest are created first.
# ETL is NOT started automatically for the large chunked
# upload, preventing a 700+ MB Excel workload from immediately
# consuming the API process after assembly.
#
# ETL can then be triggered separately.
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
        # ==================================================
        # ASSEMBLE ONLY
        # ==================================================

        result = await UploadService.complete_chunk_upload(
            upload_id=upload_id,
            filename=filename,
            total_chunks=total_chunks,
            content_type=content_type,
        )

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print("CHUNKED UPLOAD COMPLETED")
        print(
            f"DURATION : {duration:.2f}s"
        )
        print(
            f"JOB ID   : {result['job_id']}"
        )
        print(
            "ASSEMBLY FINISHED"
        )
        print(
            "ETL NOT STARTED AUTOMATICALLY"
        )
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
        print(
            f"DURATION : {duration:.2f}s"
        )
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )