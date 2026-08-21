from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

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
        logger.warning("DURABLE FILE NOT FOUND | JOB=%s | FILE=%s", job_id, filename)
        return None
    job_folder.mkdir(parents=True, exist_ok=True)
    await UploadService._s3_download_file(final_key, destination)
    return destination if destination.exists() and destination.stat().st_size > 0 else None


async def _restore_manifest_files(job_id: str, job_folder: Path, manifest: Path) -> bool:
    data = _read_json(manifest)
    files = (data or {}).get("files")
    if not isinstance(files, list) or not files:
        logger.warning("RECOVERY MANIFEST HAS NO FILES | JOB=%s", job_id)
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
        restored = await _restore_final_file(job_id, job_folder, str(filename))
        if restored is None:
            all_restored = False
    return all_restored


async def _run_etl_with_retry(job_id: str, job_folder: Path) -> None:
    """Run recovery ETL under a single-process memory gate."""
    async with _get_recovery_semaphore():
        for attempt in range(1, ETL_MAX_RETRIES + 1):
            logger.info("ETL RETRY | JOB=%s | ATTEMPT=%s/%s | NO REUPLOAD", job_id, attempt, ETL_MAX_RETRIES)
            try:
                result = await asyncio.to_thread(_run_etl, job_folder)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}
                logger.exception("ETL ATTEMPT CRASHED | JOB=%s | ATTEMPT=%s/%s", job_id, attempt, ETL_MAX_RETRIES)
            if isinstance(result, dict) and result.get("success"):
                logger.info("ETL RETRY SUCCEEDED | JOB=%s | ATTEMPT=%s/%s", job_id, attempt, ETL_MAX_RETRIES)
                return
            error = result.get("error") if isinstance(result, dict) else "ETL returned no success result"
            if attempt < ETL_MAX_RETRIES:
                logger.warning("ETL ATTEMPT FAILED | JOB=%s | ATTEMPT=%s/%s | RETRYING IN %ss | ERROR=%s", job_id, attempt, ETL_MAX_RETRIES, ETL_RETRY_DELAY_SECONDS, error)
                await asyncio.sleep(ETL_RETRY_DELAY_SECONDS)
            else:
                logger.error("ETL EXHAUSTED RETRIES | JOB=%s | ATTEMPTS=%s | ERROR=%s", job_id, ETL_MAX_RETRIES, error)


async def _recover_and_run(job_id: str) -> None:
    try:
        job_folder = RAW_UPLOAD / job_id
        manifest = await _restore_manifest(job_id, job_folder)
        if manifest is None:
            metadata_key = UploadService._job_metadata_s3_key(job_id)
            if not await UploadService._s3_head(metadata_key):
                return
            metadata = await UploadService._s3_get_json(metadata_key)
            if not isinstance(metadata, dict):
                return
            filename = metadata.get("filename") or metadata.get("original_filename")
            if not filename:
                return
            final_file = await _restore_final_file(job_id, job_folder, filename)
            if final_file is None:
                return
            manifest = await _restore_manifest(job_id, job_folder)
            if manifest is None:
                return
        data = _read_json(manifest)
        status = str((data or {}).get("status", "")).upper()
        if status != "FAILED":
            logger.info("STARTUP RECOVERY SKIP | JOB=%s | STATUS=%s", job_id, status or "UNKNOWN")
            return
        if not await _restore_manifest_files(job_id, job_folder, manifest):
            logger.error("STARTUP RECOVERY BLOCKED | JOB=%s | REQUIRED ASSEMBLED FILE MISSING", job_id)
            return
        await _run_etl_with_retry(job_id, job_folder)
    except Exception:
        logger.exception("Durable job recovery failed for %s", job_id)
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
            logger.exception("Unexpected durable job task failure for %s", job_id)
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
            try:
                data = await UploadService._s3_get_json(key)
                status = str((data or {}).get("status", "")).upper()
                if status == "FAILED":
                    logger.warning("STARTUP JOB RECOVERY | JOB=%s | STATUS=FAILED | AUTO RETRY", job_id)
                    ensure_job_processing(job_id)
                    recovered += 1
            except Exception:
                logger.exception("Could not inspect durable job %s", job_id)
        logger.info("STARTUP JOB RECOVERY SCAN COMPLETED | RECOVERED=%s", recovered)
    except Exception:
        logger.exception("Startup durable job recovery scan failed")
