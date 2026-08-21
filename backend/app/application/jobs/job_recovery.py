from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import boto3

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService, S3_BUCKET, _create_s3_client

logger = logging.getLogger(__name__)
_RUNNING_JOB_IDS: set[str] = set()
_RECOVERY_SEMAPHORE: asyncio.Semaphore | None = None

ETL_MAX_RETRIES = max(1, int(os.getenv("ETL_MAX_RETRIES", "3")))
ETL_RETRY_DELAY_SECONDS = max(1, int(os.getenv("ETL_RETRY_DELAY_SECONDS", "5")))


def _get_recovery_semaphore() -> asyncio.Semaphore:
    global _RECOVERY_SEMAPHORE
    if _RECOVERY_SEMAPHORE is None:
        _RECOVERY_SEMAPHORE = asyncio.Semaphore(1)
    return _RECOVERY_SEMAPHORE


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _run_etl(job_folder: Path) -> dict | None:
    return ETLOrchestrator.process(job_folder)


async def _restore_manifest(job_id: str, job_folder: Path) -> Path | None:
    manifest = job_folder / "manifest.json"
    if manifest.exists():
        return manifest
    manifest_key = UploadService._job_manifest_s3_key(job_id)
    if not await UploadService._s3_head(manifest_key):
        return None
    await UploadService._s3_download_file(manifest_key, manifest)
    return manifest if manifest.exists() else None


async def _restore_final_file(job_id: str, job_folder: Path, filename: str) -> Path | None:
    destination = job_folder / filename
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    final_key = UploadService._job_file_s3_key(job_id, filename)
    if not await UploadService._s3_head(final_key):
        return None
    job_folder.mkdir(parents=True, exist_ok=True)
    await UploadService._s3_download_file(final_key, destination)
    return destination if destination.exists() and destination.stat().st_size > 0 else None


async def _restore_manifest_files(job_id: str, job_folder: Path, manifest: Path) -> bool:
    data = _read_json(manifest)
    files = (data or {}).get("files")
    if not isinstance(files, list) or not files:
        return False
    all_restored = True
    for record in files:
        if not isinstance(record, dict):
            all_restored = False
            continue
        filename = record.get("filename")
        if not filename:
            all_restored = False
            continue
        if await _restore_final_file(job_id, job_folder, str(filename)) is None:
            all_restored = False
    return all_restored


async def _read_durable_job(job_id: str) -> dict | None:
    key = UploadService._job_metadata_s3_key(job_id)
    try:
        if not await UploadService._s3_head(key):
            return None
        data = await UploadService._s3_get_json(key)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("DURABLE JOB READ FAILED | JOB=%s", job_id)
        return None


async def _recover_assembly_if_needed(job_id: str, job_folder: Path, metadata: dict) -> Path | None:
    manifest = await _restore_manifest(job_id, job_folder)
    if manifest is not None:
        return manifest

    files = metadata.get("files")
    file_record = files[0] if isinstance(files, list) and files and isinstance(files[0], dict) else metadata
    filename = str(file_record.get("filename") or file_record.get("original_filename") or "").strip()
    if not filename:
        return None

    content_type = file_record.get("content_type") or metadata.get("content_type")
    final_file = await _restore_final_file(job_id, job_folder, filename)

    if final_file is None:
        upload_id = file_record.get("upload_id") or metadata.get("upload_id")
        total_chunks = file_record.get("total_chunks") or metadata.get("total_chunks")
        if upload_id and total_chunks is not None:
            logger.info("RECOVERY RESUMING CHUNKS | JOB=%s | UPLOAD=%s | CHUNKS=%s", job_id, upload_id, total_chunks)
            result = await UploadService.assemble_chunk_upload(
                upload_id=str(upload_id),
                job_id=job_id,
                filename=filename,
                total_chunks=int(total_chunks),
                content_type=content_type,
            )
            if not result.get("success", True):
                raise RuntimeError(f"Chunk assembly failed: {result}")
        else:
            logger.warning("RECOVERY WAITING FOR ASSEMBLY | JOB=%s | FILE=%s", job_id, filename)
            return None

    return await _restore_manifest(job_id, job_folder)


async def _run_etl_with_retry(job_id: str, job_folder: Path) -> bool:
    async with _get_recovery_semaphore():
        last_error = "unknown ETL failure"
        for attempt in range(1, ETL_MAX_RETRIES + 1):
            logger.info("ETL RECOVERY | JOB=%s | ATTEMPT=%s/%s", job_id, attempt, ETL_MAX_RETRIES)
            try:
                result = await asyncio.to_thread(_run_etl, job_folder)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}
                logger.exception("ETL CRASHED | JOB=%s | ATTEMPT=%s", job_id, attempt)
            if isinstance(result, dict) and result.get("success"):
                return True
            last_error = result.get("error") if isinstance(result, dict) else "ETL returned no success result"
            if attempt < ETL_MAX_RETRIES:
                await asyncio.sleep(ETL_RETRY_DELAY_SECONDS)
        logger.error("ETL RECOVERY EXHAUSTED | JOB=%s | ERROR=%s", job_id, last_error)
        return False


async def _recover_and_run(job_id: str) -> None:
    try:
        job_folder = RAW_UPLOAD / job_id
        metadata = await _read_durable_job(job_id)
        manifest = await _restore_manifest(job_id, job_folder)
        if manifest is None and metadata is None:
            return

        data = _read_json(manifest) if manifest else metadata
        status = str((data or {}).get("status", "")).upper()
        if status == "FINISHED":
            return
        if status not in {
            "UPLOADED", "DETECTING", "VALIDATING", "MERGING", "TRANSFORMING",
            "EXPORTING", "ASSEMBLY_QUEUED", "ASSEMBLY_COMPLETED", "FAILED",
        }:
            return

        if manifest is None:
            manifest = await _recover_assembly_if_needed(job_id, job_folder, metadata or {})
            if manifest is None:
                return

        if not await _restore_manifest_files(job_id, job_folder, manifest):
            logger.error("RECOVERY BLOCKED | JOB=%s | REQUIRED FILE MISSING", job_id)
            return

        await _run_etl_with_retry(job_id, job_folder)
    except Exception:
        logger.exception("DURABLE JOB RECOVERY FAILED | JOB=%s", job_id)
    finally:
        _RUNNING_JOB_IDS.discard(job_id)


def ensure_job_processing(job_id: str) -> None:
    job_id = job_id.strip()
    if not job_id or job_id in _RUNNING_JOB_IDS:
        return
    _RUNNING_JOB_IDS.add(job_id)
    task = asyncio.create_task(_recover_and_run(job_id))

    def _done(completed: asyncio.Task) -> None:
        try:
            completed.exception()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unexpected durable job task failure | JOB=%s", job_id)

    task.add_done_callback(_done)


async def recover_failed_jobs_on_startup() -> None:
    try:
        client = _create_s3_client()
        response = await asyncio.to_thread(client.list_objects_v2, Bucket=S3_BUCKET, Prefix="jobs/")
        recovered = 0
        for item in response.get("Contents", []):
            key = str(item.get("Key", ""))
            if not key.endswith("/job.json"):
                continue
            job_id = key[len("jobs/"):-len("/job.json")]
            if not job_id:
                continue
            data = await UploadService._s3_get_json(key)
            status = str((data or {}).get("status", "")).upper()
            if status != "FINISHED":
                ensure_job_processing(job_id)
                recovered += 1
        logger.info("DURABLE JOB RECOVERY SCAN | RECOVERED=%s", recovered)
    except Exception:
        logger.exception("Durable job recovery scan failed")
