from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.application.jobs.job_manager import JobManager
from app.application.jobs.job_status import JobStatus
from app.core.constants import RAW_UPLOAD
from app.etl.detector.detector import FileDetector
from app.etl.detector.month_resolver import MonthResolver
from app.etl.validator.validator import DatasetValidator


UPLOAD_FOLDER = RAW_UPLOAD

# Keep each HTTP request comfortably below Cloudflare's payload limit.
CHUNK_SIZE = 20 * 1024 * 1024  # 20 MB


class UploadService:
    """
    Upload Engine

    Normal upload:
        Upload
            ↓
        Save Files
            ↓
        Detect Dataset
            ↓
        Resolve Month
            ↓
        Validate
            ↓
        Create Manifest
            ↓
        Register Job

    Large-file upload:
        Chunk 1
        Chunk 2
        Chunk 3
           ...
        Chunk N
            ↓
        Assemble File
            ↓
        Detect Dataset
            ↓
        Resolve Month
            ↓
        Validate
            ↓
        Create Manifest
            ↓
        Register Job

    Coordinate master handling
    --------------------------
    TO_PRABAYAR.xlsx and TO_PASCABAYAR.xlsx are fixed coordinate
    master files. They intentionally resolve to month=None.

    The monthless state is valid for these files and must NOT be
    replaced with a month inferred from the JOB folder, upload time,
    or filesystem timestamp.

    ETLPipeline is responsible for applying the coordinate masters
    to the business months that are actually processed.
    """

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    # ==========================================================
    # FILENAME
    # ==========================================================

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        name = filename.lower().strip()
        name = name.replace("-", "_").replace(" ", "_")

        while "__" in name:
            name = name.replace("__", "_")

        return name

    @classmethod
    def _is_coordinate_master(
        cls,
        filename: str,
    ) -> bool:
        return (
            cls._normalize_filename(filename)
            in cls.COORDINATE_MASTER_FILES
        )

    @staticmethod
    def _safe_filename(
        filename: str | None,
    ) -> str:
        original = filename or "uploaded_file"

        safe = (
            original
            .replace("\\", "/")
            .split("/")[-1]
        )

        if not safe:
            safe = "uploaded_file"

        return safe

    # ==========================================================
    # VALIDATE / BUILD FILE METADATA
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
            dataset = FileDetector.detect(
                destination,
            )

            if dataset == FileDetector.UNKNOWN:
                validation = {
                    "status": "FAILED",
                    "missing_columns": [],
                    "error": (
                        "Unable to detect dataset from filename."
                    ),
                }

            else:
                month = MonthResolver.resolve(
                    destination,
                )

                validation = DatasetValidator.validate(
                    destination,
                    dataset,
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
            print(
                "✓ Coordinate Master :",
                filename,
            )

            # Coordinate masters are deliberately monthless.
            month = None

            if dataset == FileDetector.UNKNOWN:
                dataset = FileDetector.CUSTOMER_LOCATION

        return {
            "filename": filename,
            "size": destination.stat().st_size,
            "content_type": content_type,
            "dataset": dataset,
            "month": month,
            "is_coordinate_master": is_coordinate_master,
            "validation": validation["status"],
            "missing_columns": validation.get(
                "missing_columns",
                [],
            ),
            "error": validation.get("error"),
        }

    # ==========================================================
    # NORMAL SMALL-FILE UPLOAD
    # ==========================================================

    @classmethod
    async def save_files(
        cls,
        files: list[UploadFile],
    ):
        """
        Existing upload endpoint.

        Keep this for small files and backward compatibility.
        Large files should use chunk upload.
        """

        print("=" * 80)
        print("UPLOAD START")

        job_id = datetime.now().strftime(
            "JOB_%Y%m%d_%H%M%S"
        ) + "_" + uuid.uuid4().hex[:8]

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

            print()
            print(
                f"Processing : {file.filename}"
            )

            original_filename = (
                file.filename
                or "uploaded_file"
            )

            safe_filename = cls._safe_filename(
                original_filename,
            )

            destination = (
                job_folder
                / safe_filename
            )

            async with aiofiles.open(
                destination,
                "wb",
            ) as out:

                while True:
                    chunk = await file.read(
                        1024 * 1024,
                    )

                    if not chunk:
                        break

                    await out.write(chunk)

            print("✓ Saved")
            print(
                "✓ File Path :",
                destination,
            )

            metadata = cls._inspect_file(
                destination=destination,
                filename=safe_filename,
                content_type=file.content_type,
            )

            metadata["original_filename"] = (
                original_filename
            )

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
        """
        Receive ONE chunk only.

        Each request should be approximately 20 MB,
        avoiding the 711 MB Cloudflare request problem.
        """

        if chunk_number < 0:
            raise ValueError(
                "chunk_number must be >= 0"
            )

        if total_chunks <= 0:
            raise ValueError(
                "total_chunks must be > 0"
            )

        if chunk_number >= total_chunks:
            raise ValueError(
                "chunk_number must be smaller than total_chunks"
            )

        safe_filename = cls._safe_filename(
            filename,
        )

        chunks_folder = (
            UPLOAD_FOLDER
            / "_chunks"
            / upload_id
        )

        chunks_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        chunk_path = (
            chunks_folder
            / f"{chunk_number:08d}.part"
        )

        received = 0

        async with aiofiles.open(
            chunk_path,
            "wb",
        ) as out:

            while True:
                data = await file.read(
                    1024 * 1024,
                )

                if not data:
                    break

                received += len(data)

                await out.write(
                    data,
                )

        print(
            "CHUNK RECEIVED:",
            upload_id,
            chunk_number,
            "/",
            total_chunks,
            received,
            "bytes",
        )

        return {
            "success": True,
            "upload_id": upload_id,
            "filename": safe_filename,
            "chunk_number": chunk_number,
            "total_chunks": total_chunks,
            "received_bytes": received,
        }

    # ==========================================================
    # COMPLETE CHUNK UPLOAD
    # ==========================================================

    @classmethod
    async def complete_chunk_upload(
        cls,
        upload_id: str,
        filename: str,
        total_chunks: int,
        content_type: str | None = None,
    ) -> dict:

        if total_chunks <= 0:
            raise ValueError(
                "total_chunks must be > 0"
            )

        safe_filename = cls._safe_filename(
            filename,
        )

        chunks_folder = (
            UPLOAD_FOLDER
            / "_chunks"
            / upload_id
        )

        if not chunks_folder.exists():
            raise FileNotFoundError(
                f"Upload '{upload_id}' not found."
            )

        # ======================================================
        # VERIFY ALL CHUNKS EXIST
        # ======================================================

        missing_chunks: list[int] = []

        for index in range(total_chunks):

            chunk_path = (
                chunks_folder
                / f"{index:08d}.part"
            )

            if not chunk_path.exists():
                missing_chunks.append(
                    index,
                )

        if missing_chunks:
            raise ValueError(
                "Missing chunks: "
                + ", ".join(
                    map(
                        str,
                        missing_chunks[:20],
                    )
                )
            )

        # ======================================================
        # CREATE JOB
        # ======================================================

        job_id = datetime.now().strftime(
            "JOB_%Y%m%d_%H%M%S"
        ) + "_" + uuid.uuid4().hex[:8]

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

        print("=" * 80)
        print("ASSEMBLING CHUNKED UPLOAD")
        print("Upload ID :", upload_id)
        print("Filename  :", safe_filename)
        print("Chunks    :", total_chunks)
        print("Target    :", destination)
        print("=" * 80)

        # ======================================================
        # STREAM CHUNKS INTO FINAL FILE
        # ======================================================

        async with aiofiles.open(
            destination,
            "wb",
        ) as output:

            for index in range(total_chunks):

                chunk_path = (
                    chunks_folder
                    / f"{index:08d}.part"
                )

                async with aiofiles.open(
                    chunk_path,
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

                print(
                    f"✓ Assembled chunk "
                    f"{index + 1}/{total_chunks}"
                )

        # ======================================================
        # INSPECT FINAL FILE
        # ======================================================

        metadata = cls._inspect_file(
            destination=destination,
            filename=safe_filename,
            content_type=content_type,
        )

        metadata["original_filename"] = (
            filename
        )

        result = await cls._finalize_job(
            job_id=job_id,
            job_folder=job_folder,
            uploaded=[
                metadata,
            ],
        )

        # ======================================================
        # REMOVE TEMPORARY CHUNKS
        # ======================================================

        try:
            for chunk_path in chunks_folder.glob(
                "*.part",
            ):
                chunk_path.unlink(
                    missing_ok=True,
                )

            chunks_folder.rmdir()

        except Exception:
            traceback.print_exc()

        return result

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
            "uploaded_at": datetime.now().isoformat(),
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
        ) as f:

            await f.write(
                json.dumps(
                    manifest,
                    indent=4,
                    default=str,
                )
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
                "is_coordinate_master"
            )
        ]

        failed_files = [
            item["filename"]
            for item in uploaded
            if item.get(
                "validation"
            ) != "PASSED"
        ]

        print()
        print("Manifest :")
        print(manifest_path)

        print()
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