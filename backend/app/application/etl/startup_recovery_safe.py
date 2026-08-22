from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
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
    int(os.getenv("MAX_FAILED_RECOVERY_ATTEMPTS", "5")),
)
# Bump this whenever the recovery implementation is materially fixed. Jobs
# exhausted by the previous policy are then granted a fresh recovery pass.
RECOVERY_POLICY_VERSION = "2026-08-23-v5"
_LOCK = asyncio.Lock()


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


def _load_jobs() -> list[dict[str, Any]]:
    client = _client()
    if client is None:
        return []

    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=S3_BUCKET,
            Prefix="jobs/",
        ):
            for item in page.get("Contents", []):
                key = str(item.get("Key") or "")
                if not key.endswith("/job.json"):
                    continue

                parts = key.split("/")
                if len(parts) != 3 or parts[1] in seen:
                    continue

                job_id = parts[1]
                seen.add(job_id)

                try:
                    response = client.get_object(
                        Bucket=S3_BUCKET,
                        Key=key,
                    )
                    body = response["Body"]
                    try:
                        metadata = json.loads(
                            body.read().decode("utf-8")
                        )
                    finally:
                        body.close()
                except Exception:
                    logger.exception(
                        "STARTUP RECOVERY: failed reading %s",
                        key,
                    )
                    continue

                if not isinstance(metadata, dict):
                    continue

                if (
                    str(metadata.get("status", "")).upper()
                    not in RECOVERABLE_STATUSES
                ):
                    continue

                metadata["job_id"] = metadata.get("job_id") or job_id
                jobs.append(metadata)

    except Exception:
        logger.exception(
            "STARTUP RECOVERY: failed listing durable jobs"
        )
        return []

    jobs.sort(
        key=lambda x: str(
            x.get("uploaded_at")
            or x.get("created_at")
            or ""
        )
    )
    return jobs


async def _persist(metadata: dict[str, Any]) -> None:
    job_id = str(metadata.get("job_id") or "").strip()
    if job_id:
        await UploadService._s3_put_json(
            UploadService._job_metadata_s3_key(job_id),
            metadata,
        )


async def _reject(
    metadata: dict[str, Any],
    job_id: str,
    reason: str,
) -> None:
    metadata.update(
        {
            "status": "REJECTED",
            "progress": 0,
            "current_step": "RECOVERY_REJECTED",
            "last_error": reason,
            "rejected_at": datetime.now().isoformat(),
            "recovery_policy_version": RECOVERY_POLICY_VERSION,
        }
    )
    try:
        await _persist(metadata)
    except Exception:
        logger.exception(
            "STARTUP RECOVERY: failed persisting rejected state | job=%s",
            job_id,
        )


def _manifest_dataset(job_id: str) -> str | None:
    try:
        manifest = json.loads(
            (
                RAW_UPLOAD
                / job_id
                / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        files = manifest.get("files") or []
        if files and isinstance(files[0], dict):
            value = files[0].get("dataset")
            return (
                str(value).strip().upper()
                if value
                else None
            )
    except Exception:
        pass
    return None


def _bind_manifest_to_job(job_id: str) -> None:
    """Add job_id to each file record so legacy FileGrouper calls stay job-local."""
    path = RAW_UPLOAD / job_id / "manifest.json"
    try:
        manifest = json.loads(
            path.read_text(encoding="utf-8")
        )
        changed = False
        for record in manifest.get("files") or []:
            if (
                isinstance(record, dict)
                and record.get("job_id") != job_id
            ):
                record["job_id"] = job_id
                changed = True
        if changed:
            path.write_text(
                json.dumps(
                    manifest,
                    indent=4,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )
    except Exception:
        logger.exception(
            "STARTUP RECOVERY: could not bind manifest to job | job=%s",
            job_id,
        )


async def _recover_one(metadata: dict[str, Any]) -> str:
    job_id = str(metadata.get("job_id") or "").strip()
    files = metadata.get("files")
    file_meta = (
        files[0]
        if isinstance(files, list)
        and files
        and isinstance(files[0], dict)
        else metadata
    )

    filename = str(
        file_meta.get("filename")
        or file_meta.get("original_filename")
        or ""
    ).strip()

    if not job_id or not filename:
        return "failed"

    status = str(metadata.get("status") or "").upper()
    last_error = str(metadata.get("last_error") or "")
    attempts = int(metadata.get("recovery_attempts") or 0)
    previous_policy = str(
        metadata.get("recovery_policy_version") or ""
    )

    if (
        status == "FAILED"
        and last_error.startswith(
            "Unable to detect dataset for uploaded file(s):"
        )
    ):
        await _reject(
            metadata,
            job_id,
            last_error,
        )
        logger.warning(
            "STARTUP RECOVERY: terminal undetectable job rejected | job=%s | file=%s",
            job_id,
            filename,
        )
        return "rejected"

    if attempts >= MAX_FAILED_RECOVERY_ATTEMPTS:
        if previous_policy != RECOVERY_POLICY_VERSION:
            logger.warning(
                "STARTUP RECOVERY: resetting exhausted job under new policy | job=%s | old_attempts=%s | old_policy=%s | new_policy=%s",
                job_id,
                attempts,
                previous_policy or "<none>",
                RECOVERY_POLICY_VERSION,
            )
            attempts = 0
            metadata["recovery_attempts"] = 0
        else:
            logger.warning(
                "STARTUP RECOVERY: retry limit reached | job=%s | attempts=%s",
                job_id,
                attempts,
            )
            return "failed"

    metadata["recovery_attempts"] = attempts + 1
    metadata["recovery_policy_version"] = RECOVERY_POLICY_VERSION
    metadata["last_recovery_at"] = datetime.now().isoformat()
    await _persist(metadata)

    job_folder = RAW_UPLOAD / job_id

    try:
        content_type = file_meta.get("content_type")
        upload_id = (
            file_meta.get("upload_id")
            or metadata.get("upload_id")
        )
        total_chunks = (
            file_meta.get("total_chunks")
            or metadata.get("total_chunks")
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
            result = await UploadService.assemble_chunk_upload(
                upload_id=str(upload_id),
                job_id=job_id,
                filename=filename,
                total_chunks=int(total_chunks),
                content_type=content_type,
            )

        if (
            not isinstance(result, dict)
            or not result.get("success", True)
        ):
            raise RuntimeError(
                "Durable recovery returned unsuccessful result: "
                f"{result}"
            )

        dataset = _manifest_dataset(job_id)
        if not dataset or dataset == "UNKNOWN":
            reason = (
                "Unable to detect dataset for uploaded file(s): "
                f"{filename}. Use a supported PLN dataset or upload "
                "a valid Excel workbook."
            )
            await _reject(
                metadata,
                job_id,
                reason,
            )
            logger.warning(
                "STARTUP RECOVERY: undetectable workbook rejected before ETL | job=%s | file=%s",
                job_id,
                filename,
            )
            return "rejected"

        _bind_manifest_to_job(job_id)

        etl_result = await asyncio.to_thread(
            ETLOrchestrator.process,
            job_folder,
        )

        if (
            not isinstance(etl_result, dict)
            or not etl_result.get("success")
        ):
            raise RuntimeError(
                f"Recovered ETL failed: {etl_result}"
            )

        metadata.update(
            {
                "status": "FINISHED",
                "progress": 100,
                "current_step": "FINISHED",
                "finished_at": datetime.now().isoformat(),
                "recovery_completed_at": datetime.now().isoformat(),
            }
        )
        metadata.pop("last_error", None)
        await _persist(metadata)
        logger.info(
            "STARTUP RECOVERY: job=%s finished successfully",
            job_id,
        )
        return "recovered"

    except Exception as exc:
        metadata.update(
            {
                "status": "FAILED",
                "current_step": "RECOVERY_FAILED",
                "last_error": str(exc),
                "last_failed_at": datetime.now().isoformat(),
            }
        )
        try:
            await _persist(metadata)
        except Exception:
            logger.exception(
                "STARTUP RECOVERY: failed persisting failure | job=%s",
                job_id,
            )
        logger.exception(
            "STARTUP RECOVERY: job=%s failed",
            job_id,
        )
        return "failed"


async def recover_pending_jobs() -> dict[str, int]:
    """Drain all currently eligible durable jobs one at a time."""
    async with _LOCK:
        jobs = await asyncio.to_thread(_load_jobs)
        if not jobs:
            logger.info(
                "STARTUP RECOVERY: no unfinished durable jobs found"
            )
            return {
                "found": 0,
                "recovered": 0,
                "failed": 0,
                "rejected": 0,
            }

        recovered = failed = rejected = 0

        for metadata in jobs:
            result = await _recover_one(metadata)
            if result == "recovered":
                recovered += 1
            elif result == "rejected":
                rejected += 1
            else:
                failed += 1

        logger.info(
            "STARTUP RECOVERY COMPLETED | found=%s recovered=%s failed=%s rejected=%s",
            len(jobs),
            recovered,
            failed,
            rejected,
        )
        return {
            "found": len(jobs),
            "recovered": recovered,
            "failed": failed,
            "rejected": rejected,
        }
