from __future__ import annotations

import asyncio
import json
import os
import shutil
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.application.jobs.job_manager import JobManager
from app.application.jobs.job_status import JobStatus
from app.core.constants import RAW_UPLOAD
from app.etl.detector.detector import FileDetector


# ==========================================================
# CONFIGURATION
# ==========================================================

UPLOAD_FOLDER = RAW_UPLOAD

CHUNK_SIZE = 20 * 1024 * 1024

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "").strip()
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

# Prefixes inside Supabase Storage bucket.
S3_CHUNK_PREFIX = "chunks"
S3_JOB_PREFIX = "jobs"


# ==========================================================
# S3 CLIENT
# ==========================================================


def _create_s3_client():
    """
    Create an S3-compatible client for Supabase Storage.

    The client is created lazily so the application can still
    start locally when S3 environment variables are absent.
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


# ==========================================================
# UPLOAD SERVICE
# ==========================================================


class UploadService:
    """
    Persistent upload service.

    SMALL FILE
        upload
        -> local temporary file
        -> inspect
        -> manifest

    LARGE FILE
        chunk 1..N
        -> each chunk uploaded to Supabase Storage
        -> /complete
        -> verify chunks in Supabase
        -> create durable job metadata
        -> background assembly
        -> download chunks from Supabase
        -> assemble local file
        -> lightweight filename detection
        -> manifest
        -> ETL

    IMPORTANT:

    Chunk data is NOT treated as durable local filesystem data.

    Supabase Storage is the source of truth for chunked uploads.

    Therefore a FastAPI Cloud restart/redeployment does not
    destroy an unfinished upload.

    Large Excel files are NEVER inspected during assembly.
    MonthResolver and DatasetValidator remain deferred to ETL.
    """

    # ==========================================================
    # COORDINATE MASTER FILES
    # ==========================================================

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    # ==========================================================
    # FILENAME
    # ==========================================================

    @staticmethod
    def _normalize_filename(
        filename: str,
    ) -> str:
        name = (
            filename
            .lower()
            .strip()
        )

        name = (
            name
            .replace("-", "_")
            .replace(" ", "_")
        )

        while "__" in name:
            name = name.replace(
                "__",
                "_",
            )

        return name

    @classmethod
    def _is_coordinate_master(
        cls,
        filename: str,
    ) -> bool:
        return (
            cls._normalize_filename(
                filename,
            )
            in cls.COORDINATE_MASTER_FILES
        )

    @staticmethod
    def _safe_filename(
        filename: str | None,
    ) -> str:
        original = (
            filename
            or "uploaded_file"
        )

        safe = (
            original
            .replace("\\", "/")
            .split("/")[-1]
        )

        if not safe:
            safe = "uploaded_file"

        return safe

    # ==========================================================
    # JOB ID
    # ==========================================================

    @staticmethod
    def _new_job_id() -> str:
        return (
            datetime.now().strftime(
                "JOB_%Y%m%d_%H%M%S",
            )
            + "_"
            + uuid.uuid4().hex[:8]
        )

    # ==========================================================
    # S3 KEY HELPERS
    # ==========================================================

    @staticmethod
    def _chunk_s3_key(
        upload_id: str,
        chunk_number: int,
    ) -> str:
        return (
            f"{S3_CHUNK_PREFIX}/"
            f"{upload_id}/"
            f"{chunk_number:08d}.part"
        )

    @staticmethod
    def _job_file_s3_key(
        job_id: str,
        filename: str,
    ) -> str:
        return (
            f"{S3_JOB_PREFIX}/"
            f"{job_id}/"
            f"{filename}"
        )

    @staticmethod
    def _job_manifest_s3_key(
        job_id: str,
    ) -> str:
        return (
            f"{S3_JOB_PREFIX}/"
            f"{job_id}/manifest.json"
        )

    @staticmethod
    def _job_metadata_s3_key(
        job_id: str,
    ) -> str:
        return (
            f"{S3_JOB_PREFIX}/"
            f"{job_id}/job.json"
        )

    # ==========================================================
    # S3 HELPERS
    # ==========================================================

    @classmethod
    async def _s3_put_file(
        cls,
        local_path: Path,
        s3_key: str,
    ) -> None:
        """
        Upload a local file to Supabase Storage.

        boto3 is synchronous, therefore it is executed in a
        worker thread so the FastAPI event loop is not blocked.
        """

        def _upload() -> None:
            client = _create_s3_client()

            client.upload_file(
                str(local_path),
                S3_BUCKET,
                s3_key,
                ExtraArgs={
                    "ContentType": (
                        "application/octet-stream"
                    ),
                },
            )

        await asyncio.to_thread(
            _upload,
        )

    @classmethod
    async def _s3_download_file(
        cls,
        s3_key: str,
        local_path: Path,
    ) -> None:
        """
        Download a file from Supabase Storage.
        """

        local_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        def _download() -> None:
            client = _create_s3_client()

            client.download_file(
                S3_BUCKET,
                s3_key,
                str(local_path),
            )

        await asyncio.to_thread(
            _download,
        )

    @classmethod
    async def _s3_head(
        cls,
        s3_key: str,
    ) -> bool:
        """
        Check whether an object exists.
        """

        def _head() -> bool:
            client = _create_s3_client()

            try:
                client.head_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                )
                return True

            except ClientError as exc:
                error_code = (
                    exc.response
                    .get("Error", {})
                    .get("Code")
                )

                if error_code in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }:
                    return False

                raise

        return await asyncio.to_thread(
            _head,
        )

    @classmethod
    async def _s3_put_json(
        cls,
        s3_key: str,
        payload: dict,
    ) -> None:
        """
        Store durable JSON metadata in Supabase Storage.
        """

        body = json.dumps(
            payload,
            indent=4,
            default=str,
        ).encode("utf-8")

        def _put() -> None:
            client = _create_s3_client()

            client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=body,
                ContentType="application/json",
            )

        await asyncio.to_thread(
            _put,
        )

    @classmethod
    async def _s3_get_json(
        cls,
        s3_key: str,
    ) -> dict:
        """
        Read durable JSON metadata from Supabase Storage.
        """

        def _get() -> dict:
            client = _create_s3_client()

            response = client.get_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
            )

            raw = response["Body"].read()

            return json.loads(
                raw.decode("utf-8"),
            )

        return await asyncio.to_thread(
            _get,
        )

    @classmethod
    async def _s3_delete_prefix(
        cls,
        prefix: str,
    ) -> None:
        """
        Delete all objects under a prefix.

        Used only after successful assembly.
        """

        def _delete() -> None:
            client = _create_s3_client()

            paginator = client.get_paginator(
                "list_objects_v2",
            )

            objects: list[dict] = []

            for page in paginator.paginate(
                Bucket=S3_BUCKET,
                Prefix=prefix,
            ):
                objects.extend(
                    page.get(
                        "Contents",
                        [],
                    )
                )

            if not objects:
                return

            for offset in range(
                0,
                len(objects),
                1000,
            ):
                batch = objects[
                    offset : offset + 1000
                ]

                client.delete_objects(
                    Bucket=S3_BUCKET,
                    Delete={
                        "Objects": [
                            {
                                "Key": item["Key"],
                            }
                            for item in batch
                        ],
                    },
                )

        await asyncio.to_thread(
            _delete,
        )

    # ==========================================================
    # NORMAL FILE INSPECTION
    #
    # Small files only.
    # ==========================================================

    @classmethod
    def _inspect_file(
        cls,
        destination: Path,
        filename: str,
        content_type: str | None,
    ) -> dict:

        dataset = None
        month = None

        validation = {
            "status": "FAILED",
            "missing_columns": [],
        }

        try:
            # Lazy imports intentionally kept out of the large
            # chunk assembly path.

            from app.etl.detector.month_resolver import (
                MonthResolver,
            )
            from app.etl.validator.validator import (
                DatasetValidator,
            )

            dataset = FileDetector.detect(
                destination,
            )

            if dataset == FileDetector.UNKNOWN:
                validation = {
                    "status": "FAILED",
                    "missing_columns": [],
                    "error": (
                        "Unable to detect dataset "
                        "from filename."
                    ),
                }

            else:
                month = MonthResolver.resolve(
                    destination,
                )

                validation = (
                    DatasetValidator.validate(
                        destination,
                        dataset,
                    )
                )

            print(
                "✓ Dataset :",
                dataset,
            )

            print(
                "✓ Month :",
                month,
            )

            print(
                "✓ Validation :",
                validation["status"],
            )

            if validation.get("error"):
                print(
                    "✗ Validation Error :",
                    validation["error"],
                )

        except Exception as exc:
            traceback.print_exc()

            dataset = None
            month = None

            validation = {
                "status": "FAILED",
                "missing_columns": [],
                "error": str(exc),
            }

        is_coordinate_master = (
            cls._is_coordinate_master(
                filename,
            )
        )

        if is_coordinate_master:
            month = None

            if dataset == FileDetector.UNKNOWN:
                dataset = (
                    FileDetector.CUSTOMER_LOCATION
                )

        return {
            "filename": filename,
            "size": destination.stat().st_size,
            "content_type": content_type,
            "dataset": dataset,
            "month": month,
            "is_coordinate_master": (
                is_coordinate_master
            ),
            "validation": validation["status"],
            "missing_columns": validation.get(
                "missing_columns",
                [],
            ),
            "error": validation.get(
                "error",
            ),
        }

    # ==========================================================
    # NORMAL SMALL FILE UPLOAD
    # ==========================================================

    @classmethod
    async def save_files(
        cls,
        files: list[UploadFile],
    ) -> dict:

        print("=" * 80)
        print("UPLOAD START")
        print("UPLOAD MODE : NORMAL")
        print("=" * 80)

        job_id = cls._new_job_id()

        job_folder = (
            UPLOAD_FOLDER
            / job_id
        )

        job_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        uploaded: list[dict] = []

        for file in files:

            original_filename = (
                file.filename
                or "uploaded_file"
            )

            safe_filename = (
                cls._safe_filename(
                    original_filename,
                )
            )

            destination = (
                job_folder
                / safe_filename
            )

            print(
                "Processing :",
                original_filename,
            )

            async with aiofiles.open(
                destination,
                "wb",
            ) as output:

                while True:
                    data = await file.read(
                        1024 * 1024,
                    )

                    if not data:
                        break

                    await output.write(
                        data,
                    )

            print(
                "✓ Saved :",
                destination,
            )

            metadata = cls._inspect_file(
                destination=destination,
                filename=safe_filename,
                content_type=file.content_type,
            )

            metadata[
                "original_filename"
            ] = original_filename

            uploaded.append(
                metadata,
            )

        return await cls._finalize_job(
            job_id=job_id,
            job_folder=job_folder,
            uploaded=uploaded,
        )

    # ==========================================================
    # CHUNK UPLOAD
    #
    # CHUNK IS STORED IN SUPABASE.
    #
    # Local disk is only a temporary staging area.
    # ==========================================================

    @classmethod
    async def save_chunk(
        cls,
        upload_id: str,
        filename: str,
        chunk_number: int,
        total_chunks: int,
        file: UploadFile,
    ) -> dict:

        if chunk_number < 0:
            raise ValueError(
                "chunk_number must be >= 0",
            )

        if total_chunks <= 0:
            raise ValueError(
                "total_chunks must be > 0",
            )

        if chunk_number >= total_chunks:
            raise ValueError(
                "chunk_number must be smaller "
                "than total_chunks",
            )

        safe_filename = cls._safe_filename(
            filename,
        )

        # Temporary local staging.
        temp_folder = (
            UPLOAD_FOLDER
            / "_temp_chunks"
            / upload_id
        )

        temp_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_path = (
            temp_folder
            / f"{chunk_number:08d}.part"
        )

        received = 0

        try:
            async with aiofiles.open(
                temp_path,
                "wb",
            ) as output:

                while True:
                    data = await file.read(
                        1024 * 1024,
                    )

                    if not data:
                        break

                    received += len(data)

                    await output.write(
                        data,
                    )

            s3_key = cls._chunk_s3_key(
                upload_id,
                chunk_number,
            )

            print("=" * 80)
            print("CHUNK UPLOAD")
            print("Upload ID :", upload_id)
            print(
                "Chunk     :",
                f"{chunk_number + 1}/{total_chunks}",
            )
            print("Size      :", received)
            print("S3 Key    :", s3_key)
            print("=" * 80)

            await cls._s3_put_file(
                temp_path,
                s3_key,
            )

            print(
                "✓ CHUNK STORED IN SUPABASE:",
                s3_key,
            )

            return {
                "success": True,
                "upload_id": upload_id,
                "filename": safe_filename,
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "received_bytes": received,
                "storage": "supabase",
            }

        finally:
            try:
                temp_path.unlink(
                    missing_ok=True,
                )
            except Exception:
                traceback.print_exc()

    # ==========================================================
    # PREPARE CHUNK UPLOAD
    #
    # IMPORTANT:
    #
    # This operation does NOT assemble the file.
    #
    # It verifies the chunks EXIST IN SUPABASE, creates a
    # durable job metadata object, then returns immediately.
    # ==========================================================

    @classmethod
    async def prepare_chunk_upload(
        cls,
        upload_id: str,
        filename: str,
        total_chunks: int,
        content_type: str | None = None,
    ) -> dict:

        if total_chunks <= 0:
            raise ValueError(
                "total_chunks must be > 0",
            )

        safe_filename = cls._safe_filename(
            filename,
        )

        print("=" * 80)
        print("PREPARING CHUNKED UPLOAD")
        print("Upload ID    :", upload_id)
        print("Filename     :", safe_filename)
        print("Total chunks :", total_chunks)
        print("Storage      : SUPABASE")
        print("=" * 80)

        missing_chunks: list[int] = []

        # Verify every chunk directly in durable storage.
        for index in range(
            total_chunks,
        ):

            s3_key = cls._chunk_s3_key(
                upload_id,
                index,
            )

            exists = await cls._s3_head(
                s3_key,
            )

            if not exists:
                missing_chunks.append(
                    index,
                )

        if missing_chunks:
            raise ValueError(
                "Missing chunks in Supabase Storage: "
                + ", ".join(
                    map(
                        str,
                        missing_chunks[:20],
                    )
                )
            )

        job_id = cls._new_job_id()

        job_folder = (
            UPLOAD_FOLDER
            / job_id
        )

        job_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        upload_metadata = {
            "upload_id": upload_id,
            "filename": safe_filename,
            "original_filename": filename,
            "total_chunks": total_chunks,
            "content_type": content_type,
            "job_id": job_id,
            "status": "ASSEMBLY_QUEUED",
            "created_at": (
                datetime.now().isoformat()
            ),
        }

        # Local copy for the current instance.
        metadata_path = (
            job_folder
            / "chunk_upload.json"
        )

        async with aiofiles.open(
            metadata_path,
            "w",
            encoding="utf-8",
        ) as output:

            await output.write(
                json.dumps(
                    upload_metadata,
                    indent=4,
                )
            )

        # DURABLE copy.
        await cls._s3_put_json(
            cls._job_metadata_s3_key(
                job_id,
            ),
            upload_metadata,
        )

        print("=" * 80)
        print("CHUNK UPLOAD ACCEPTED")
        print("Upload ID    :", upload_id)
        print("Job ID       :", job_id)
        print("Filename     :", safe_filename)
        print("Total chunks :", total_chunks)
        print("Storage      : SUPABASE")
        print("Assembly     : QUEUED")
        print("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "uploaded_at": (
                datetime.now().isoformat()
            ),
            "total_files": 1,
            "files": [],
            "status": "ASSEMBLY_QUEUED",
        }

    # ==========================================================
    # COMPLETE
    # ==========================================================

    @classmethod
    async def complete_chunk_upload(
        cls,
        upload_id: str,
        filename: str,
        total_chunks: int,
        content_type: str | None = None,
    ) -> dict:

        return await cls.prepare_chunk_upload(
            upload_id=upload_id,
            filename=filename,
            total_chunks=total_chunks,
            content_type=content_type,
        )

    # ==========================================================
    # BACKGROUND ASSEMBLY
    #
    # SUPABASE -> LOCAL FILE
    #
    # Then ETL can consume the assembled local file.
    # ==========================================================

    @classmethod
    async def assemble_chunk_upload(
        cls,
        upload_id: str,
        job_id: str,
        filename: str,
        total_chunks: int,
        content_type: str | None = None,
    ) -> dict:

        safe_filename = cls._safe_filename(
            filename,
        )

        job_folder = (
            UPLOAD_FOLDER
            / job_id
        )

        destination = (
            job_folder
            / safe_filename
        )

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        try:

            print("=" * 80)
            print("BACKGROUND CHUNK ASSEMBLY START")
            print("Upload ID :", upload_id)
            print("Job ID    :", job_id)
            print("Filename  :", safe_filename)
            print("Chunks    :", total_chunks)
            print("Target    :", destination)
            print("Storage   : SUPABASE")
            print("=" * 80)

            job_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            # --------------------------------------------------
            # VERIFY ALL CHUNKS IN SUPABASE
            # --------------------------------------------------

            for index in range(
                total_chunks,
            ):

                s3_key = cls._chunk_s3_key(
                    upload_id,
                    index,
                )

                exists = await cls._s3_head(
                    s3_key,
                )

                if not exists:
                    raise FileNotFoundError(
                        f"Missing Supabase chunk {index}: "
                        f"{s3_key}",
                    )

            # --------------------------------------------------
            # ASSEMBLE
            #
            # Download one chunk at a time.
            # Never load the 746 MB workbook into memory.
            # --------------------------------------------------

            if destination.exists():
                destination.unlink()

            async with aiofiles.open(
                destination,
                "wb",
            ) as output:

                for index in range(
                    total_chunks,
                ):

                    s3_key = cls._chunk_s3_key(
                        upload_id,
                        index,
                    )

                    temp_chunk = (
                        job_folder
                        / (
                            f".chunk_{index:08d}"
                            ".part"
                        )
                    )

                    try:

                        print(
                            f"Downloading chunk "
                            f"{index + 1}/"
                            f"{total_chunks}"
                        )

                        await cls._s3_download_file(
                            s3_key,
                            temp_chunk,
                        )

                        async with aiofiles.open(
                            temp_chunk,
                            "rb",
                        ) as source:

                            while True:
                                data = await source.read(
                                    1024 * 1024,
                                )

                                if not data:
                                    break

                                await output.write(
                                    data,
                                )

                        progress = (
                            (index + 1)
                            / total_chunks
                            * 100
                        )

                        print(
                            f"✓ Assembled "
                            f"{index + 1}/"
                            f"{total_chunks} "
                            f"({progress:.1f}%)"
                        )

                    finally:

                        try:
                            temp_chunk.unlink(
                                missing_ok=True,
                            )
                        except Exception:
                            traceback.print_exc()

            # --------------------------------------------------
            # FINAL FILE
            # --------------------------------------------------

            file_size = (
                destination.stat().st_size
            )

            print(
                "✓ FINAL FILE:",
                destination,
            )

            print(
                "✓ SIZE:",
                file_size,
                "bytes",
            )

            # --------------------------------------------------
            # LIGHTWEIGHT DETECTION ONLY
            #
            # NO MonthResolver.
            # NO DatasetValidator.
            # NO pandas.read_excel().
            # --------------------------------------------------

            dataset = FileDetector.detect(
                destination,
            )

            is_coordinate_master = (
                cls._is_coordinate_master(
                    safe_filename,
                )
            )

            if (
                dataset
                == FileDetector.UNKNOWN
                and is_coordinate_master
            ):
                dataset = (
                    FileDetector.CUSTOMER_LOCATION
                )

            month = None

            print(
                "✓ Dataset :",
                dataset,
            )

            print(
                "✓ Month : deferred to ETL",
            )

            # --------------------------------------------------
            # MANIFEST
            # --------------------------------------------------

            metadata = {
                "filename": safe_filename,
                "size": file_size,
                "content_type": content_type,
                "dataset": dataset,
                "month": month,
                "is_coordinate_master": (
                    is_coordinate_master
                ),
                "validation": "PENDING",
                "missing_columns": [],
                "error": None,
                "original_filename": filename,
                "storage": "supabase",
                "upload_id": upload_id,
            }

            result = await cls._finalize_job(
                job_id=job_id,
                job_folder=job_folder,
                uploaded=[
                    metadata,
                ],
            )

            if not manifest_path.exists():
                raise FileNotFoundError(
                    f"Manifest was not created: "
                    f"{manifest_path}",
                )

            print(
                "✓ MANIFEST READY:",
                manifest_path,
            )

            # --------------------------------------------------
            # COPY MANIFEST TO SUPABASE
            # --------------------------------------------------

            await cls._s3_put_json(
                cls._job_manifest_s3_key(
                    job_id,
                ),
                {
                    **json.loads(
                        manifest_path.read_text(
                            encoding="utf-8",
                        )
                    ),
                    "storage": "supabase",
                },
            )

            # --------------------------------------------------
            # STORE FINAL FILE IN SUPABASE
            #
            # This makes the assembled Excel durable too.
            # --------------------------------------------------

            final_s3_key = (
                cls._job_file_s3_key(
                    job_id,
                    safe_filename,
                )
            )

            await cls._s3_put_file(
                destination,
                final_s3_key,
            )

            print(
                "✓ FINAL FILE STORED:",
                final_s3_key,
            )

            # --------------------------------------------------
            # DELETE CHUNKS FROM SUPABASE
            #
            # Only AFTER successful assembly.
            # --------------------------------------------------

            await cls._s3_delete_prefix(
                f"{S3_CHUNK_PREFIX}/"
                f"{upload_id}/",
            )

            print(
                "✓ SOURCE CHUNKS DELETED FROM SUPABASE"
            )

            print("=" * 80)
            print(
                "BACKGROUND CHUNK ASSEMBLY FINISHED"
            )
            print(
                "JOB ID :",
                job_id,
            )
            print(
                "MANIFEST:",
                manifest_path,
            )
            print(
                "FINAL S3 FILE:",
                final_s3_key,
            )
            print("=" * 80)

            return {
                **result,
                "status": "ASSEMBLY_COMPLETED",
                "manifest_path": str(
                    manifest_path,
                ),
                "storage": "supabase",
                "s3_key": final_s3_key,
            }

        except Exception as exc:

            print("=" * 80)
            print(
                "BACKGROUND CHUNK ASSEMBLY FAILED"
            )
            print(
                "JOB ID :",
                job_id,
            )
            print(
                "ERROR  :",
                exc,
            )
            print("=" * 80)

            traceback.print_exc()

            try:
                JobManager.update(
                    job_folder=job_folder,
                    status=JobStatus.FAILED,
                    progress=0,
                    step="ASSEMBLY_FAILED",
                )
            except Exception:
                traceback.print_exc()

            raise

    # ==========================================================
    # RECOVER EXISTING ASSEMBLED JOB
    #
    # First checks local file.
    # If missing, downloads durable file from Supabase.
    # ==========================================================

    @classmethod
    async def recover_assembled_job(
        cls,
        job_id: str,
        filename: str,
        content_type: str | None = None,
    ) -> dict:

        safe_filename = cls._safe_filename(
            filename,
        )

        job_folder = (
            UPLOAD_FOLDER
            / job_id
        )

        job_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            job_folder
            / safe_filename
        )

        # --------------------------------------------------
        # IF LOCAL FILE EXISTS
        # --------------------------------------------------

        if not destination.exists():

            final_s3_key = (
                cls._job_file_s3_key(
                    job_id,
                    safe_filename,
                )
            )

            exists = await cls._s3_head(
                final_s3_key,
            )

            if not exists:
                raise FileNotFoundError(
                    f"Final file not found locally "
                    f"or in Supabase Storage: "
                    f"{safe_filename}",
                )

            print(
                "Recovering final file from Supabase:",
                final_s3_key,
            )

            await cls._s3_download_file(
                final_s3_key,
                destination,
            )

        file_size = (
            destination.stat().st_size
        )

        dataset = FileDetector.detect(
            destination,
        )

        is_coordinate_master = (
            cls._is_coordinate_master(
                safe_filename,
            )
        )

        if (
            dataset
            == FileDetector.UNKNOWN
            and is_coordinate_master
        ):
            dataset = (
                FileDetector.CUSTOMER_LOCATION
            )

        metadata = {
            "filename": safe_filename,
            "size": file_size,
            "content_type": content_type,
            "dataset": dataset,
            "month": None,
            "is_coordinate_master": (
                is_coordinate_master
            ),
            "validation": "PENDING",
            "missing_columns": [],
            "error": None,
            "original_filename": filename,
            "storage": "supabase",
        }

        result = await cls._finalize_job(
            job_id=job_id,
            job_folder=job_folder,
            uploaded=[
                metadata,
            ],
        )

        if not (
            job_folder
            / "manifest.json"
        ).exists():
            raise FileNotFoundError(
                "Manifest was not created."
            )

        return {
            **result,
            "status": "ASSEMBLY_COMPLETED",
            "manifest_path": str(
                job_folder
                / "manifest.json",
            ),
        }

    # ==========================================================
    # FINALIZE JOB
    # ==========================================================

    @classmethod
    async def _finalize_job(
        cls,
        job_id: str,
        job_folder: Path,
        uploaded: list[dict],
    ) -> dict:

        manifest = {
            "job_id": job_id,
            "status": JobStatus.UPLOADED.value,
            "progress": 0,
            "current_step": "UPLOAD",
            "uploaded_at": (
                datetime.now().isoformat()
            ),
            "started_at": None,
            "finished_at": None,
            "total_files": len(uploaded),
            "processed_files": 0,
            "files": uploaded,
        }

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        async with aiofiles.open(
            manifest_path,
            "w",
            encoding="utf-8",
        ) as output:

            await output.write(
                json.dumps(
                    manifest,
                    indent=4,
                    default=str,
                )
            )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found after creation: "
                f"{manifest_path}",
            )

        JobManager.update(
            job_folder=job_folder,
            status=JobStatus.UPLOADED,
            progress=0,
            step="UPLOAD",
        )

        coordinate_masters = [
            item["filename"]
            for item in uploaded
            if item.get(
                "is_coordinate_master",
            )
        ]

        failed_files = [
            item["filename"]
            for item in uploaded
            if item.get(
                "validation",
            )
            not in (
                "PASSED",
                "PENDING",
            )
        ]

        print()
        print(
            "Manifest :",
            manifest_path,
        )

        print(
            "Coordinate Masters :",
            coordinate_masters,
        )

        print(
            "Validation Failures :",
            failed_files,
        )

        print()
        print("UPLOAD FINISHED")
        print("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "uploaded_at": manifest[
                "uploaded_at"
            ],
            "total_files": len(uploaded),
            "files": uploaded,
        }