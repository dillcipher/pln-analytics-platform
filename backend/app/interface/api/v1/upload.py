from __future__ import annotations

import time
import traceback
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
)

from app.core.constants import RAW_UPLOAD
from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.schemas.upload_schema import UploadResponse
from app.services.upload_service import UploadService

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


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


@router.post(
    "/files",
    response_model=UploadResponse,
)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):

    start = time.perf_counter()

    print("=" * 80)
    print("UPLOAD API CALLED")
    print(f"TOTAL FILES : {len(files)}")
    print("=" * 80)

    try:

        # ==================================================
        # SAVE FILES
        # ==================================================

        result = await UploadService.save_files(
            files,
        )

        # ==================================================
        # START ETL IN BACKGROUND
        # ==================================================

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
        print("=" * 80)

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )