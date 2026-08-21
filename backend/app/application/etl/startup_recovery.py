from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import boto3

from app.application.etl.etl_orchestrator import ETLOrchestrator
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "").strip()
S3_REGION = os.getenv("S3_REGION", "ap-southeast-1").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
S3_BUCKET = os.getenv("S3_BUCKET", "pln-analytics-uploads").strip()
S3_JOB_PREFIX = "jobs"

# A job is safe to replay when it has reached the upload/ETL lifecycle but
# has not been durably marked FINISHED. FAILED jobs are deliberately excluded:
# they need an explicit retry instead of creating an infinite restart loop.
RECOVERABLE_STATUSES = {
    "UPLOADED",
    "DETECTING",
    "VALIDATING",
    "MERGING",
    "TRANSFORMING",
    "EXPORTING",
    "ASSEMBLY_QUEUED",
}


def _client():
    if not S3_ENDPOINT or not S3_ACCESS_KEY_ID or not S3_SECRET_ACCESS_KEY:
        return None
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    )


def _load_pending_jobs() -> list[dict[str, Any]]:
    """Read durable job metadata without loading any uploaded workbook."""
    client = _client()
    if client is None:
        logger.warning("Startup recovery skipped: durable upload storage is not configured.")
        return []

    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=S3_BUCKET,
            Prefix=f"{S3_JOB_PREFIX}/",
        ):
            for item in page.get("Contents", []):
                key = item.get("Key", "")
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
                    raw = response["Body"].read()
                    metadata = json.loads(raw.decode("utf-8"))
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

    # Oldest first so an interrupted historical queue is drained in order.
    jobs.sort(key=lambda item: str(item.get("uploaded_at") or ""))
    return jobs


async def recover_pending_jobs() -> dict[str, int]:
    """Recover durable unfinished uploads and run their ETL automatically.

    The final assembled workbook is already durable in Supabase Storage for
    chunked uploads. The recovery method downloads it only when the local
    instance does not have it, recreates the manifest, then sends the job
    through the exact same ETL path used immediately after upload.

    ETLOrchestrator is serialized by runtime_guard, so multiple recovered jobs
    cannot execute concurrently and exhaust the container memory.
    """
    jobs = await asyncio.to_thread(_load_pending_jobs)

    if not jobs:
        logger.info("STARTUP RECOVERY: no unfinished durable jobs found")
        return {"found": 0, "recovered": 0, "failed": 0}

    logger.info("STARTUP RECOVERY: %s unfinished durable job(s) found", len(jobs))

    recovered = 0
    failed = 0

    for metadata in jobs:
        job_id = str(metadata.get("job_id") or "").strip()
        filename = str(
            metadata.get("filename")
            or metadata.get("original_filename")
            or ""
        ).strip()
        content_type = metadata.get("content_type")

        if not job_id or not filename:
            failed += 1
            logger.error("STARTUP RECOVERY: invalid durable job metadata: %r", metadata)
            continue

        try:
            logger.info(
                "STARTUP RECOVERY: recovering job=%s file=%s status=%s",
                job_id,
                filename,
                metadata.get("status"),
            )

            result = await UploadService.recover_assembled_job(
                job_id=job_id,
                filename=filename,
                content_type=content_type,
            )

            if not result.get("success", True):
                raise RuntimeError(
                    f"Durable recovery returned unsuccessful result: {result}"
                )

            job_folder = UploadService.UPLOAD_FOLDER / job_id
            manifest = job_folder / "manifest.json"
            if not manifest.exists():
                raise FileNotFoundError(f"Recovered manifest not found: {manifest}")

            etl_result = await asyncio.to_thread(
                ETLOrchestrator.process,
                job_folder,
            )

            if not isinstance(etl_result, dict) or not etl_result.get("success"):
                raise RuntimeError(
                    f"Recovered ETL failed: {etl_result}"
                )

            recovered += 1
            logger.info("STARTUP RECOVERY: job=%s finished successfully", job_id)

        except Exception:
            failed += 1
            logger.exception("STARTUP RECOVERY: job=%s failed", job_id)

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
