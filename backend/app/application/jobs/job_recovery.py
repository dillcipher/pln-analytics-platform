from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)
_RUNNING_JOB_IDS: set[str] = set()

# ETL retries operate on the already assembled durable workbook. No chunks
# are uploaded again and no new upload job is created.
ETL_MAX_RETRIES = max(1, int(os.getenv("ETL_MAX_RETRIES", "3")))
ETL_RETRY_DELAY_SECONDS = max(1, int(os.getenv("ETL_RETRY_DELAY_SECONDS", "5")))


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
    """Restore an already-completed assembly from durable storage only."""
    manifest = job_folder / "manifest.json"
    if manifest.exists():
        return manifest

    manifest_key = UploadService._job_manifest_s3_key(job_id)
    if not await UploadService._s3_head(manifest_key):
        return None

    await UploadService._s3_download_file(manifest_key, manifest)
    return manifest if manifest.exists() else None


async def _restore_final_file(job_id: str, job_folder: Path, filename: str) -> Path | None:
    """Restore the final assembled workbook, never reconstructing live chunks."""
    destination = job_folder / filename
    if destination.exists() and destination.stat().st_size > 0:
        return destination

    final_key = UploadService._job_file_s3_key(job_id, filename)
    if not await UploadService._s3_head(final_key):
        return None

    await UploadService._s3_download_file(final_key, destination)
    return destination if destination.exists() and destination.stat().st_size > 0 else None


async def _run_etl_with_retry(job_id: str, job_folder: Path) -> None:
    """Retry ETL in-place using the durable assembled files and checkpoint."""
    for attempt in range(1, ETL_MAX_RETRIES + 1):
        logger.info(
            "ETL RETRY | JOB=%s | ATTEMPT=%s/%s | NO REUPLOAD",
            job_id,
            attempt,
            ETL_MAX_RETRIES,
        )

        try:
            result = await asyncio.to_thread(_run_etl, job_folder)
        except Exception as exc:
            result = {
                "success": False,
                "error": str(exc),
            }
            logger.exception(
                "ETL ATTEMPT CRASHED | JOB=%s | ATTEMPT=%s/%s",
                job_id,
                attempt,
                ETL_MAX_RETRIES,
            )

        if isinstance(result, dict) and result.get("success"):
            logger.info(
                "ETL RETRY SUCCEEDED | JOB=%s | ATTEMPT=%s/%s",
                job_id,
                attempt,
                ETL_MAX_RETRIES,
            )
            return

        error = (
            result.get("error")
            if isinstance(result, dict)
            else "ETL returned no success result"
        )

        if attempt < ETL_MAX_RETRIES:
            logger.warning(
                "ETL ATTEMPT FAILED | JOB=%s | ATTEMPT=%s/%s | RETRYING IN %ss | ERROR=%s",
                job_id,
                attempt,
                ETL_MAX_RETRIES,
                ETL_RETRY_DELAY_SECONDS,
                error,
            )
            await asyncio.sleep(ETL_RETRY_DELAY_SECONDS)
        else:
            logger.error(
                "ETL EXHAUSTED RETRIES | JOB=%s | ATTEMPTS=%s | ERROR=%s",
                job_id,
                ETL_MAX_RETRIES,
                error,
            )


async def _recover_and_run(job_id: str) -> None:
    try:
        job_folder = RAW_UPLOAD / job_id
        manifest = await _restore_manifest(job_id, job_folder)

        # IMPORTANT: /jobs is polled immediately after /complete. During
        # that window the original instance may still be assembling the
        # workbook. Never run ETL from job metadata or live chunks before
        # the assembly has produced its durable manifest/final file.
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
                # Assembly is still in progress. Let the original assembly
                # task finish; a later poll can retry recovery safely.
                return

            manifest = await _restore_manifest(job_id, job_folder)
            if manifest is None:
                return

        await _run_etl_with_retry(job_id, job_folder)
    except Exception:
        logger.exception("Durable job recovery failed for %s", job_id)
    finally:
        _RUNNING_JOB_IDS.discard(job_id)


def ensure_job_processing(job_id: str) -> None:
    """Wake a completed/recoverable job without racing live assembly."""
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
