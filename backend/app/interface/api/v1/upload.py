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
# NORMAL ETL
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

        print("=" * 80)
        print("BACKGROUND ETL FAILED")
        print(job_folder)
        print("=" * 80)

        traceback.print_exc()


# ==========================================================
# CHUNKED PIPELINE
#
# URUTAN WAJIB:
#
# 1. Assemble
# 2. Inspect
# 3. Create manifest
# 4. Verify manifest
# 5. ETL
#
# ETL TIDAK BOLEH DIMULAI SEBELUM ASSEMBLY SELESAI.
# ==========================================================

async def _run_chunked_pipeline(
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
        print("BACKGROUND CHUNKED PIPELINE START")
        print("UPLOAD ID    :", upload_id)
        print("JOB ID       :", job_id)
        print("FILE         :", filename)
        print("TOTAL CHUNKS :", total_chunks)
        print("=" * 80)

        # ======================================================
        # 1. ASSEMBLY
        #
        # Fungsi ini TIDAK return sebelum manifest tersedia.
        # ======================================================

        assembly_result = (
            await UploadService.assemble_chunk_upload(
                upload_id=upload_id,
                job_id=job_id,
                filename=filename,
                total_chunks=total_chunks,
                content_type=content_type,
            )
        )

        print("=" * 80)
        print("ASSEMBLY COMPLETED")
        print("JOB ID :", job_id)
        print(
            "STATUS :",
            assembly_result.get("status"),
        )
        print("=" * 80)

        # ======================================================
        # 2. VERIFY MANIFEST
        # ======================================================

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        if not manifest_path.exists():

            raise FileNotFoundError(
                f"Manifest not found after assembly: "
                f"{manifest_path}",
            )

        print(
            "✓ Manifest confirmed:",
            manifest_path,
        )

        # ======================================================
        # 3. ETL
        #
        # Baru boleh jalan sekarang.
        # ======================================================

        print("=" * 80)
        print("STARTING ETL AFTER ASSEMBLY")
        print("JOB ID :", job_id)
        print("=" * 80)

        # ETLOrchestrator.process() adalah synchronous.
        #
        # Jalankan di thread supaya event loop tidak diblok.
        await asyncio.to_thread(
            ETLOrchestrator.process,
            job_folder,
        )

        print("=" * 80)
        print("BACKGROUND CHUNKED PIPELINE FINISHED")
        print("JOB ID :", job_id)
        print("=" * 80)

    except Exception as exc:

        print("=" * 80)
        print("BACKGROUND CHUNKED PIPELINE FAILED")
        print("JOB ID :", job_id)
        print("ERROR  :", exc)
        print("=" * 80)

        traceback.print_exc()


# ==========================================================
# NORMAL UPLOAD
#
# Untuk file kecil.
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
    print(
        f"FILE        : {file.filename}"
    )
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

    except Exception as exc:

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print(
            f"UPLOAD FAILED ({duration:.2f}s)"
        )
        print(
            f"ERROR : {exc}"
        )
        print(
            f"DURATION : {duration:.2f}s"
        )
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
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
    print("UPLOAD ID    :", upload_id)
    print("FILE         :", filename)
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

    except ValueError as exc:

        traceback.print_exc()

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
# PENTING:
#
# Endpoint ini HANYA:
#
# 1. Verify semua chunks
# 2. Create job
# 3. Return cepat
# 4. Schedule SATU background pipeline
#
# Background pipeline:
#
#     ASSEMBLY
#        ↓
#     MANIFEST
#        ↓
#     ETL
#
# Tidak ada ETL terpisah sebelum assembly.
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

        # ======================================================
        # CREATE JOB
        #
        # TIDAK ASSEMBLE DI REQUEST.
        # ======================================================

        result = (
            await UploadService.complete_chunk_upload(
                upload_id=upload_id,
                filename=filename,
                total_chunks=total_chunks,
                content_type=content_type,
            )
        )

        job_id = result["job_id"]

        # ======================================================
        # ONE BACKGROUND PIPELINE
        #
        # Assembly → Manifest → ETL
        # ======================================================

        background_tasks.add_task(
            _run_chunked_pipeline,
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
        print(
            "CHUNKED UPLOAD ACCEPTED"
        )
        print(
            f"DURATION : {duration:.2f}s"
        )
        print(
            f"JOB ID   : {job_id}"
        )
        print(
            "BACKGROUND PIPELINE SCHEDULED"
        )
        print(
            "ASSEMBLY -> MANIFEST -> ETL"
        )
        print("=" * 80)

        return result

    except FileNotFoundError as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except ValueError as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        duration = (
            time.perf_counter()
            - start
        )

        print("=" * 80)
        print(
            "COMPLETE UPLOAD FAILED"
        )
        print(
            f"ERROR    : {exc}"
        )
        print(
            f"DURATION : {duration:.2f}s"
        )
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )