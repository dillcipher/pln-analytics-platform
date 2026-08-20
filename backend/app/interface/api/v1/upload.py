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
    try:
        print("=" * 80)
        print("BACKGROUND ETL START")
        print(job_folder)
        print("=" * 80)

        ETLOrchestrator.process(
            job_folder,
        )

        print("=" * 80)
        print("BACKGROUND ETL FINISHED")
        print("=" * 80)

    except Exception:
        traceback.print_exc()


# ==========================================================
# NORMAL UPLOAD
#
# Untuk file kecil.
# Jangan digunakan untuk file 711 MB.
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
        print(
            f"UPLOAD FAILED ({duration:.2f}s)"
        )
        print(
            f"ERROR : {e}"
        )
        print(
            f"DURATION : {duration:.2f}s"
        )
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ==========================================================
# CHUNK UPLOAD
#
# Satu request hanya membawa satu chunk.
#
# Contoh:
#
# chunk 0  -> 20 MB
# chunk 1  -> 20 MB
# chunk 2  -> 20 MB
# ...
#
# Jadi Cloudflare tidak menerima request 711 MB.
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
# Setelah semua chunk berhasil dikirim:
#
# /chunk
# /chunk
# /chunk
# ...
# /complete
#
# Endpoint ini:
#   1. Memastikan semua chunk ada
#   2. Menggabungkan chunk
#   3. Membuat job
#   4. Detect dataset
#   5. Validate
#   6. Membuat manifest
#   7. Menjalankan ETL background
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
    print(f"UPLOAD ID    : {upload_id}")
    print(f"FILE         : {filename}")
    print(f"TOTAL CHUNKS : {total_chunks}")
    print("=" * 80)

    try:
        result = await UploadService.complete_chunk_upload(
            upload_id=upload_id,
            filename=filename,
            total_chunks=total_chunks,
            content_type=content_type,
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

        print("=" * 80)
        print(
            "CHUNKED UPLOAD COMPLETED"
        )
        print(
            f"DURATION : {duration:.2f}s"
        )
        print(
            f"JOB ID   : {result['job_id']}"
        )
        print(
            "ETL RUNNING IN BACKGROUND..."
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
        print(
            "COMPLETE UPLOAD FAILED"
        )
        print(
            f"ERROR    : {e}"
        )
        print(
            f"DURATION : {duration:.2f}s"
        )
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )