from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/process",
    tags=["Process"],
)


async def _ensure_job_local(job_id: str):
    """Ensure a durable uploaded job exists on this API replica.

    FastAPI Cloud replicas have ephemeral local disks, while the upload
    service stores the final assembled workbook and job metadata in Supabase
    Storage. A process request must therefore recover the job when it lands
    on a fresh replica instead of returning a misleading 404.
    """
    job_folder = RAW_UPLOAD / job_id
    manifest_path = job_folder / "manifest.json"

    if manifest_path.exists():
        return job_folder

    try:
        metadata = await UploadService._s3_get_json(
            UploadService._job_metadata_s3_key(job_id),
        )
    except Exception as exc:
        logger.exception("Could not load durable job metadata | job=%s", job_id)
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' tidak ditemukan di storage durable.",
        ) from exc

    files = metadata.get("files")
    if isinstance(files, list) and files and isinstance(files[0], dict):
        file_metadata = files[0]
    else:
        filename = metadata.get("filename") or metadata.get("original_filename")
        if not filename:
            raise HTTPException(
                status_code=422,
                detail=f"Metadata job '{job_id}' tidak memiliki nama file.",
            )
        file_metadata = {
            "filename": filename,
            "original_filename": metadata.get("original_filename") or filename,
            "content_type": metadata.get("content_type"),
            "upload_id": metadata.get("upload_id"),
            "total_chunks": metadata.get("total_chunks"),
        }

    filename = str(
        file_metadata.get("filename")
        or file_metadata.get("original_filename")
        or ""
    ).strip()
    content_type = file_metadata.get("content_type")

    if not filename:
        raise HTTPException(
            status_code=422,
            detail=f"Metadata job '{job_id}' tidak memiliki nama file yang valid.",
        )

    # First try the durable final assembled workbook. This is the normal path
    # for jobs that already reached ASSEMBLY_COMPLETED/UPLOADED.
    try:
        result = await UploadService.recover_assembled_job(
            job_id=job_id,
            filename=filename,
            content_type=content_type,
        )
        if result.get("success", True) and manifest_path.exists():
            return job_folder
    except FileNotFoundError:
        # The final workbook may not have been assembled yet. If chunk
        # metadata is available, resume assembly from durable chunks below.
        pass
    except Exception as exc:
        logger.exception("Durable job recovery failed | job=%s", job_id)
        raise HTTPException(
            status_code=503,
            detail=f"Gagal memulihkan file job '{job_id}': {exc}",
        ) from exc

    upload_id = file_metadata.get("upload_id") or metadata.get("upload_id")
    total_chunks = file_metadata.get("total_chunks") or metadata.get("total_chunks")

    if upload_id and total_chunks is not None:
        try:
            result = await UploadService.assemble_chunk_upload(
                upload_id=str(upload_id),
                job_id=job_id,
                filename=filename,
                total_chunks=int(total_chunks),
                content_type=content_type,
            )
            if result.get("success", True) and manifest_path.exists():
                return job_folder
        except Exception as exc:
            logger.exception("Durable chunk assembly failed | job=%s", job_id)
            raise HTTPException(
                status_code=503,
                detail=f"Gagal merakit file job '{job_id}': {exc}",
            ) from exc

    raise HTTPException(
        status_code=409,
        detail=(
            f"Job '{job_id}' belum memiliki file final yang siap diproses "
            "dan data chunk tidak lengkap."
        ),
    )


@router.post("/{job_id}")
async def process_job(job_id: str):
    job_id = str(job_id or "").strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id tidak boleh kosong.")

    logger.info("=" * 80)
    logger.info("Starting ETL Job : %s", job_id)
    started = time.perf_counter()

    job_folder = await _ensure_job_local(job_id)

    try:
        # Run the CPU/file-heavy ETL outside the event loop. This keeps the
        # health checks and other API requests responsive while a large DLPD
        # workbook is being transformed.
        result = await __import__("asyncio").to_thread(
            ETLOrchestrator.process,
            job_folder,
        )

        duration = round(time.perf_counter() - started, 2)

        logger.info("ETL finished (%s sec)", duration)
        logger.info("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "status": "FINISHED",
            "duration_seconds": duration,
            "message": "ETL process completed successfully.",
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ETL failed : %s", job_id)
        raise HTTPException(
            status_code=500,
            detail=f"ETL job '{job_id}' gagal: {exc}",
        ) from exc
