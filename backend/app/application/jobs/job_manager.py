from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import boto3
from botocore.client import Config

from app.application.jobs.job_status import JobStatus

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "").strip()
S3_REGION = os.getenv("S3_REGION", "ap-southeast-1").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
S3_BUCKET = os.getenv("S3_BUCKET", "pln-analytics-uploads").strip()
S3_JOB_PREFIX = "jobs"


class JobManager:
    """Central job-state manager with durable Supabase/S3 state."""

    @staticmethod
    def _create_s3_client():
        if not S3_ENDPOINT:
            raise RuntimeError("S3_ENDPOINT environment variable is not configured.")
        if not S3_ACCESS_KEY_ID:
            raise RuntimeError("S3_ACCESS_KEY_ID environment variable is not configured.")
        if not S3_SECRET_ACCESS_KEY:
            raise RuntimeError("S3_SECRET_ACCESS_KEY environment variable is not configured.")

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
                read_timeout=60,
                s3={"addressing_style": "path"},
            ),
        )

    @staticmethod
    def _job_manifest_key(job_id: str) -> str:
        return f"{S3_JOB_PREFIX}/{job_id}/manifest.json"

    @staticmethod
    def _job_metadata_key(job_id: str) -> str:
        return f"{S3_JOB_PREFIX}/{job_id}/job.json"

    @staticmethod
    def _extract_job_id(data: dict, job_folder: Path) -> str:
        job_id = data.get("job_id")
        return str(job_id) if job_id else job_folder.name

    @staticmethod
    def _put_json(key: str, data: dict) -> None:
        client = JobManager._create_s3_client()
        body = json.dumps(
            data,
            ensure_ascii=False,
            indent=4,
            default=str,
        ).encode("utf-8")
        client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=body,
            ContentLength=len(body),
            ContentType="application/json",
        )

    @staticmethod
    def _persist_durable_state(job_id: str, data: dict) -> None:
        # Preserve recovery metadata across every normal JobManager update.
        job_metadata = {
            "job_id": job_id,
            "status": data.get("status"),
            "progress": data.get("progress", 0),
            "current_step": data.get("current_step", ""),
            "uploaded_at": data.get("uploaded_at"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "total_files": data.get("total_files", 0),
            "processed_files": data.get("processed_files", 0),
            "files": data.get("files", []),
            "recovery_attempts": data.get("recovery_attempts", 0),
            "last_error": data.get("last_error"),
            "last_failed_at": data.get("last_failed_at"),
        }

        JobManager._put_json(
            JobManager._job_metadata_key(job_id),
            job_metadata,
        )
        JobManager._put_json(
            JobManager._job_manifest_key(job_id),
            data,
        )

    @staticmethod
    def update(
        job_folder: Path,
        *,
        status: JobStatus,
        progress: int,
        step: str,
    ):
        manifest = job_folder / "manifest.json"
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)

        data["status"] = status
        data["progress"] = int(progress)
        data["current_step"] = step

        if progress > 0 and data.get("started_at") is None:
            data["started_at"] = datetime.now().isoformat()

        if progress >= 100:
            data["finished_at"] = datetime.now().isoformat()

        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
                default=str,
            )

        job_id = JobManager._extract_job_id(data, job_folder)

        try:
            JobManager._persist_durable_state(job_id, data)
        except Exception as exc:
            # Local state remains authoritative for the current process, but
            # production logs must expose any loss of durable synchronization.
            print("=" * 80)
            print("WARNING: DURABLE JOB STATE SYNC FAILED")
            print("JOB ID      :", job_id)
            print("STATUS      :", status)
            print("PROGRESS    :", progress)
            print("STEP        :", step)
            print("ERROR       :", repr(exc))
            print("=" * 80)
