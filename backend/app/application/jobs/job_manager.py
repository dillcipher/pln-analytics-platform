from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import boto3

from app.application.jobs.job_status import JobStatus


# ==========================================================
# S3 / SUPABASE STORAGE CONFIGURATION
# ==========================================================

S3_ENDPOINT = os.getenv(
    "S3_ENDPOINT",
    "",
).strip()

S3_REGION = os.getenv(
    "S3_REGION",
    "ap-southeast-1",
).strip()

S3_ACCESS_KEY_ID = os.getenv(
    "S3_ACCESS_KEY_ID",
    "",
).strip()

S3_SECRET_ACCESS_KEY = os.getenv(
    "S3_SECRET_ACCESS_KEY",
    "",
).strip()

S3_BUCKET = os.getenv(
    "S3_BUCKET",
    "pln-analytics-uploads",
).strip()

S3_JOB_PREFIX = "jobs"


class JobManager:
    """
    Central job-state manager.

    Every update is persisted to two places:

        1. Local manifest.json
        2. Durable Supabase/S3 job state

    Local storage is kept for fast access by the current worker.

    Supabase/S3 is the durable source so job state survives:

        - container restart
        - worker restart
        - instance switching
        - background task execution on another instance
    """

    # ======================================================
    # S3 CLIENT
    # ======================================================

    @staticmethod
    def _create_s3_client():
        """
        Create an S3-compatible client for Supabase Storage.

        The same environment variables used by UploadService
        are used here.
        """

        if not S3_ENDPOINT:
            raise RuntimeError(
                "S3_ENDPOINT environment variable is not configured."
            )

        if not S3_ACCESS_KEY_ID:
            raise RuntimeError(
                "S3_ACCESS_KEY_ID environment variable is not configured."
            )

        if not S3_SECRET_ACCESS_KEY:
            raise RuntimeError(
                "S3_SECRET_ACCESS_KEY environment variable is not configured."
            )

        return boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        )

    # ======================================================
    # S3 KEY
    # ======================================================

    @staticmethod
    def _job_manifest_key(
        job_id: str,
    ) -> str:
        return (
            f"{S3_JOB_PREFIX}/"
            f"{job_id}/manifest.json"
        )

    @staticmethod
    def _job_metadata_key(
        job_id: str,
    ) -> str:
        return (
            f"{S3_JOB_PREFIX}/"
            f"{job_id}/job.json"
        )

    # ======================================================
    # JOB ID
    # ======================================================

    @staticmethod
    def _extract_job_id(
        data: dict,
        job_folder: Path,
    ) -> str:
        """
        Resolve job_id from manifest first, then folder name.
        """

        job_id = data.get(
            "job_id",
        )

        if job_id:
            return str(job_id)

        return job_folder.name

    # ======================================================
    # DURABLE JSON WRITE
    # ======================================================

    @staticmethod
    def _put_json(
        key: str,
        data: dict,
    ) -> None:
        """
        Write JSON directly to Supabase Storage using boto3.

        This method is synchronous because JobManager.update()
        itself is synchronous.
        """

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
            ContentType="application/json",
        )

    # ======================================================
    # DURABLE JOB STATE
    # ======================================================

    @staticmethod
    def _persist_durable_state(
        job_id: str,
        data: dict,
    ) -> None:
        """
        Persist the latest state to Supabase.

        Both objects are updated:

            jobs/{job_id}/job.json
            jobs/{job_id}/manifest.json

        job.json is the lightweight durable state used by the
        job-status endpoint before/while the manifest is available.

        manifest.json remains the durable complete job document.
        """

        # --------------------------------------------------
        # JOB METADATA
        # --------------------------------------------------

        job_metadata = {
            "job_id": job_id,
            "status": data.get(
                "status",
            ),
            "progress": data.get(
                "progress",
                0,
            ),
            "current_step": data.get(
                "current_step",
                "",
            ),
            "uploaded_at": data.get(
                "uploaded_at",
            ),
            "started_at": data.get(
                "started_at",
            ),
            "finished_at": data.get(
                "finished_at",
            ),
            "total_files": data.get(
                "total_files",
                0,
            ),
            "processed_files": data.get(
                "processed_files",
                0,
            ),
            "files": data.get(
                "files",
                [],
            ),
        }

        JobManager._put_json(
            JobManager._job_metadata_key(
                job_id,
            ),
            job_metadata,
        )

        # --------------------------------------------------
        # COMPLETE MANIFEST
        # --------------------------------------------------

        JobManager._put_json(
            JobManager._job_manifest_key(
                job_id,
            ),
            data,
        )

    # ======================================================
    # UPDATE
    # ======================================================

    @staticmethod
    def update(
        job_folder: Path,
        *,
        status: JobStatus,
        progress: int,
        step: str,
    ):
        """
        Update job status.

        The update is written locally first and then persisted
        durably to Supabase Storage.

        Example lifecycle:

            ASSEMBLY_QUEUED
                ↓
            MERGING / 20%
                ↓
            MERGING dataset
                ↓
            EXPORTING / 90%
                ↓
            FINISHED / 100%

        Failure lifecycle:

            ...
                ↓
            FAILED
        """

        # ==================================================
        # MANIFEST PATH
        # ==================================================

        manifest = (
            job_folder
            / "manifest.json"
        )

        # ==================================================
        # READ CURRENT MANIFEST
        # ==================================================

        with open(
            manifest,
            encoding="utf-8",
        ) as f:

            data = json.load(
                f,
            )

        # ==================================================
        # UPDATE STATUS
        # ==================================================

        data["status"] = status

        data["progress"] = int(
            progress,
        )

        data["current_step"] = step

        # ==================================================
        # START TIME
        # ==================================================

        if (
            progress > 0
            and data.get(
                "started_at",
            ) is None
        ):
            data["started_at"] = (
                datetime.now().isoformat()
            )

        # ==================================================
        # FINISH TIME
        # ==================================================

        if progress >= 100:

            data["finished_at"] = (
                datetime.now().isoformat()
            )

        # ==================================================
        # WRITE LOCAL MANIFEST
        # ==================================================

        with open(
            manifest,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
                default=str,
            )

        # ==================================================
        # DURABLE SUPABASE SYNC
        # ==================================================

        job_id = JobManager._extract_job_id(
            data,
            job_folder,
        )

        try:

            JobManager._persist_durable_state(
                job_id,
                data,
            )

        except Exception as exc:

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Do not hide the local state update.
            #
            # The local manifest is already valid.
            #
            # But log the durable-storage failure loudly so
            # production logs reveal the problem.
            # ------------------------------------------------

            print(
                "=" * 80,
            )

            print(
                "WARNING: DURABLE JOB STATE SYNC FAILED",
            )

            print(
                "JOB ID      :",
                job_id,
            )

            print(
                "STATUS      :",
                status,
            )

            print(
                "PROGRESS    :",
                progress,
            )

            print(
                "STEP        :",
                step,
            )

            print(
                "ERROR       :",
                repr(exc),
            )

            print(
                "=" * 80,
            )