from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.application.etl.async_job_runner import start_etl_background, is_etl_running
from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/process",
    tags=["Process"],
)


async def _ensure_job_local(job_id: str):
    """Recover a durable job onto the current ephemeral API replica."""
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

    try:
        result = await UploadService.recover_assembled_job(
            job_id=job_id,
            filename=filename,
            content_type=content_type,
        )
        if result.get("success", True) and manifest_path.exists():
            return job_folder
    except FileNotFoundError:
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


@router.post("/{job_id}", status_code=202)
async def process_job(job_id: str):
    """Queue ETL and return immediately.

    Never execute the long-running ETL inside the HTTP request. Cloudflare and
    the hosting proxy must only wait for durable file recovery and task enqueue.
    """
    job_id = str(job_id or "").strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id tidak boleh kosong.")

    logger.info("=" * 80)
    logger.info("Queueing ETL Job : %s", job_id)

    job_folder = await _ensure_job_local(job_id)

    if is_etl_running(job_id):
        return {
            "success": True,
            "job_id": job_id,
            "status": "PROCESSING",
            "message": "ETL job is already running.",
        }

    try:
        started = start_etl_background(job_id, job_folder)
    except Exception as exc:
        logger.exception("Could not queue ETL | job=%s", job_id)
        raise HTTPException(
            status_code=500,
            detail=f"ETL job '{job_id}' gagal dimasukkan ke queue: {exc}",
        ) from exc

    if not started:
        return {
            "success": True,
            "job_id": job_id,
            "status": "PROCESSING",
            "message": "ETL job is already running.",
        }

    logger.info("ETL job queued successfully | job=%s", job_id)
    logger.info("=" * 80)

    return {
        "success": True,
        "job_id": job_id,
        "status": "QUEUED",
        "message": "ETL job accepted and running in background.",
    }
