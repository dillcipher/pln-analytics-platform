from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from app.application.pipeline.pipeline import Pipeline
from app.core.constants import RAW_UPLOAD

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/process",
    tags=["Process"],
)


@router.post("/{job_id}")
async def process_job(job_id: str):

    job_folder = RAW_UPLOAD / job_id

    if not job_folder.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    logger.info("=" * 80)
    logger.info("Starting ETL Job : %s", job_id)

    started = time.perf_counter()

    try:

        result = Pipeline.run(job_folder)

        duration = round(
            time.perf_counter() - started,
            2,
        )

        logger.info(
            "ETL finished (%s sec)",
            duration,
        )

        logger.info("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "status": "FINISHED",
            "duration_seconds": duration,
            "message": "ETL process completed successfully.",
            "result": result,
        }

    except Exception as e:

        logger.exception(
            "ETL failed : %s",
            job_id,
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )