from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)
_RUNNING_JOB_IDS: set[str] = set()


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _run_etl(job_folder: Path) -> None:
    ETLOrchestrator.process(job_folder)


async def _recover_and_run(job_id: str) -> None:
    try:
        job_folder = RAW_UPLOAD / job_id
        manifest = job_folder / "manifest.json"

        if manifest.exists():
            await asyncio.to_thread(_run_etl, job_folder)
            return

        metadata_key = UploadService._job_metadata_s3_key(job_id)
        if not await UploadService._s3_head(metadata_key):
            return

        metadata = await UploadService._s3_get_json(metadata_key)
        if not isinstance(metadata, dict):
            return

        filename = metadata.get("filename") or metadata.get("original_filename")
        if not filename:
            return

        await UploadService.recover_assembled_job(
            job_id=job_id,
            filename=filename,
            content_type=metadata.get("content_type"),
        )

        if manifest.exists():
            await asyncio.to_thread(_run_etl, job_folder)
    except Exception:
        logger.exception("Durable job recovery failed for %s", job_id)
    finally:
        _RUNNING_JOB_IDS.discard(job_id)


def ensure_job_processing(job_id: str) -> None:
    """Wake an unfinished durable job without creating duplicate ETL tasks."""
    job_id = job_id.strip()
    if not job_id or job_id in _RUNNING_JOB_IDS:
        return

    job_folder = RAW_UPLOAD / job_id
    manifest = job_folder / "manifest.json"

    # A local manifest is enough to resume ETL immediately.
    # For a cloud restart, _recover_and_run restores the assembled file first.
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
