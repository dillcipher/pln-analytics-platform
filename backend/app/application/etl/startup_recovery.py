from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import boto3
from botocore.client import Config

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.core.constants import RAW_UPLOAD
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "").strip()
S3_REGION = os.getenv("S3_REGION", "ap-southeast-1").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
S3_BUCKET = os.getenv("S3_BUCKET", "pln-analytics-uploads").strip()
S3_JOB_PREFIX = "jobs"

RECOVERABLE_STATUSES = {
    "UPLOADED",
    "DETECTING",
    "VALIDATING",
    "MERGING",
    "TRANSFORMING",
    "EXPORTING",
    "ASSEMBLY_QUEUED",
    "ASSEMBLY_COMPLETED",
    "FAILED",
}
MAX_FAILED_RECOVERY_ATTEMPTS = max(
    1,
    int(os.getenv("MAX_FAILED_RECOVERY_ATTEMPTS", "3")),
)

_RECOVERY_LOCK = asyncio.Lock()


def _client():
    if not S3_ENDPOINT or not S3_ACCESS_KEY_ID or not S3_SECRET_ACCESS_KEY:
        return None
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=600,
            s3={"addressing_style": "path"},
        ),
    )


def _load_pending_jobs() -> list[dict[str, Any]]:
    """Read only lightweight durable job metadata from object storage."""
    client = _client()
    if client is None:
        logger.warning("STARTUP RECOVERY: durable upload storage is not configured.")
        return []

    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_JOB_PREFIX}/"):
            for item in page.get("Contents", []):
                key = str(item.get("Key") or "")
                if not key.startswith(f"{S3_JOB_PREFIX}/") or not key.endswith("/job.json"):
                    continue
                parts = key.split("/")
                if len(parts) != 3:
                    continue
                job_id = parts[1]
                if not job_id or job_id in seen:
                    continue
                seen.add(job_id)

                try:
                    response = client.get_object(Bucket=S3_BUCKET, Key=key)
                    body = response["Body"]
                    try:
                        metadata = json.loads(body.read().decode("utf-8"))
                    finally:
                        body.close()
                except Exception:
                    logger.exception("STARTUP RECOVERY: failed reading %s", key)
                    continue

                if not isinstance(metadata, dict):
                    continue

                status = str(metadata.get("status", "")).upper()
                if status not in RECOVERABLE_STATUSES:
                    continue

                metadata["job_id"] = metadata.get("job_id") or job_id
                jobs.append(metadata)

    except Exception:
        logger.exception("STARTUP RECOVERY: failed listing durable jobs")
        return []

    jobs.sort(
        key=lambda item: str(item.get("uploaded_at") or item.get("created_at") or "")
    )
    return jobs


def _extract_file_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    files = metadata.get("files")
    if isinstance(files, list) and files and isinstance(files[0], dict):
        return files[0]

    filename = metadata.get("filename") or metadata.get("original_filename")
    if not filename:
        return None

    return {
        "filename": filename,
        "original_filename": metadata.get("original_filename") or filename,
        "content_type": metadata.get("content_type"),
        "upload_id": metadata.get("upload_id"),
        "total_chunks": metadata.get("total_chunks"),
    }


async def _mark_recovery_attempt(metadata: dict[str, Any], job_id: str) -> int:
    attempts = int(metadata.get("recovery_attempts") or 0) + 1
    metadata["recovery_attempts"] = attempts
    try:
        await UploadService._s3_put_json(
            UploadService._job_metadata_s3_key(job_id),
            metadata,
        )
    except Exception:
        logger.exception(
            "STARTUP RECOVERY: could not persist retry counter | job=%s",
            job_id,
        )
    return attempts


async def _recover_one(metadata: dict[str, Any]) -> bool:
    job_id = str(metadata.get("job_id") or "").strip()
    file_metadata = _extract_file_metadata(metadata)

    if not job_id or not file_metadata:
        logger.error("STARTUP RECOVERY: invalid durable job metadata: %r", metadata)
        return False

    filename = str(
        file_metadata.get("filename")
        or file_metadata.get("original_filename")
        or ""
    ).strip()
    content_type = file_metadata.get("content_type")
    upload_id = file_metadata.get("upload_id") or metadata.get("upload_id")
    total_chunks = file_metadata.get("total_chunks") or metadata.get("total_chunks")

    if not filename:
        logger.error("STARTUP RECOVERY: job=%s has no filename", job_id)
        return False

    status = str(metadata.get("status") or "").upper()
    attempts = int(metadata.get("recovery_attempts") or 0)
    if status == "FAILED" and attempts >= MAX_FAILED_RECOVERY_ATTEMPTS:
        logger.error(
            "STARTUP RECOVERY: retry limit reached | job=%s | attempts=%s",
            job_id,
            attempts,
        )
        return False

    await _mark_recovery_attempt(metadata, job_id)

    job_folder = RAW_UPLOAD / job_id
    manifest_path = job_folder / "manifest.json"

    try:
        logger.info(
            "STARTUP RECOVERY: recovering job=%s file=%s status=%s",
            job_id,
            filename,
            status,
        )

        try:
            result = await UploadService.recover_assembled_job(
                job_id=job_id,
                filename=filename,
                content_type=content_type,
            )
        except FileNotFoundError:
            if not upload_id or total_chunks is None:
                raise

            logger.warning(
                "STARTUP RECOVERY: final file missing; resuming chunks | "
                "job=%s upload_id=%s chunks=%s",
                job_id,
                upload_id,
                total_chunks,
            )
            result = await UploadService.assemble_chunk_upload(
                upload_id=str(upload_id),
                job_id=job_id,
                filename=filename,
                total_chunks=int(total_chunks),
                content_type=content_type,
            )

        if not isinstance(result, dict) or not result.get("success", True):
            raise RuntimeError(f"Durable recovery returned unsuccessful result: {result}")

        if not manifest_path.exists():
            raise FileNotFoundError(f"Recovered manifest not found: {manifest_path}")

        etl_result = await asyncio.to_thread(ETLOrchestrator.process, job_folder)
        if not isinstance(etl_result, dict) or not etl_result.get("success"):
            raise RuntimeError(f"Recovered ETL failed: {etl_result}")

        logger.info("STARTUP RECOVERY: job=%s finished successfully", job_id)
        return True

    except Exception:
        logger.exception("STARTUP RECOVERY: job=%s failed", job_id)
        return False


async def recover_pending_jobs() -> dict[str, int]:
    """Recover unfinished durable jobs without blocking API availability."""
    async with _RECOVERY_LOCK:
        jobs = await asyncio.to_thread(_load_pending_jobs)
        if not jobs:
            logger.info("STARTUP RECOVERY: no unfinished durable jobs found")
            return {"found": 0, "recovered": 0, "failed": 0}

        logger.info(
            "STARTUP RECOVERY: %s unfinished durable job(s) found",
            len(jobs),
        )

        recovered = 0
        failed = 0
        for metadata in jobs:
            if await _recover_one(metadata):
                recovered += 1
            else:
                failed += 1

        logger.info(
            "STARTUP RECOVERY COMPLETED | found=%s recovered=%s failed=%s",
            len(jobs),
            recovered,
            failed,
        )
        return {
            "found": len(jobs),
            "recovered": recovered,
            "failed": failed,
        }
