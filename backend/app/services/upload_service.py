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

CHUNK_SIZE = 20 * 1024 * 1024


class UploadService:
    """
    Upload service.

    SMALL FILE
        upload
        -> inspect
        -> manifest

    LARGE FILE
        chunk 1..N
        -> /complete
        -> return immediately
        -> background assembly
        -> lightweight filename detection
        -> manifest
        -> ETL

    IMPORTANT:
    Large chunked upload MUST NOT call MonthResolver or
    DatasetValidator during assembly.

    Those operations may read a 700+ MB Excel file.
    """

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
    # NORMAL FILE INSPECTION
    #
    # Small files ONLY.
    #
    # Large chunked files must NOT use this during assembly.
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
    # PREPARE CHUNK UPLOAD
    #
    # IMPORTANT:
    # This is intentionally FAST.
    #
    # It ONLY:
    # - verifies chunks
    # - creates job folder
    # - writes chunk_upload.json
    #
    # NO ASSEMBLY.
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

        chunks_folder = (
            UPLOAD_FOLDER
            / "_chunks"
            / upload_id
        )

        if not chunks_folder.exists():
            raise FileNotFoundError(
                f"Upload '{upload_id}' not found.",
            )

        missing_chunks: list[int] = []

        for index in range(
            total_chunks,
        ):
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
            "created_at": (
                datetime.now().isoformat()
            ),
        }

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

        print("=" * 80)
        print("CHUNK UPLOAD ACCEPTED")
        print("Upload ID    :", upload_id)
        print("Job ID       :", job_id)
        print("Filename     :", safe_filename)
        print("Total chunks :", total_chunks)
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
    #
    # Alias retained for compatibility.
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
    # CRITICAL:
    #
    # DO NOT:
    #
    # MonthResolver.resolve()
    # DatasetValidator.validate()
    # pandas.read_excel()
    #
    # here.
    #
    # The 746 MB Excel file must ONLY be copied together.
    # Dataset detection is filename based.
    #
    # Manifest is created immediately afterward.
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

        chunks_folder = (
            UPLOAD_FOLDER
            / "_chunks"
            / upload_id
        )

        job_folder = (
            UPLOAD_FOLDER
            / job_id
        )

        destination = (
            job_folder
            / safe_filename
        )

        try:
            print("=" * 80)
            print("BACKGROUND CHUNK ASSEMBLY START")
            print("Upload ID :", upload_id)
            print("Job ID    :", job_id)
            print("Filename  :", safe_filename)
            print("Chunks    :", total_chunks)
            print("Target    :", destination)
            print("=" * 80)

            if not chunks_folder.exists():
                raise FileNotFoundError(
                    f"Chunk folder not found: "
                    f"{chunks_folder}",
                )

            job_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            # --------------------------------------------------
            # VERIFY CHUNKS
            # --------------------------------------------------

            for index in range(
                total_chunks,
            ):
                chunk_path = (
                    chunks_folder
                    / f"{index:08d}.part"
                )

                if not chunk_path.exists():
                    raise FileNotFoundError(
                        f"Missing chunk {index}",
                    )

            # --------------------------------------------------
            # ASSEMBLE
            # --------------------------------------------------

            async with aiofiles.open(
                destination,
                "wb",
            ) as output:

                for index in range(
                    total_chunks,
                ):
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

            # IMPORTANT:
            # Do NOT resolve month here.
            #
            # MonthResolver may read the entire Excel.
            #
            # ETL will resolve month later.
            month = None

            print(
                "✓ Dataset :",
                dataset,
            )

            print(
                "✓ Month : deferred to ETL",
            )

            # --------------------------------------------------
            # CREATE MANIFEST
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
            }

            result = await cls._finalize_job(
                job_id=job_id,
                job_folder=job_folder,
                uploaded=[
                    metadata,
                ],
            )

            manifest_path = (
                job_folder
                / "manifest.json"
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
            # DELETE CHUNKS
            # --------------------------------------------------

            try:
                for chunk_path in (
                    chunks_folder.glob(
                        "*.part",
                    )
                ):
                    chunk_path.unlink(
                        missing_ok=True,
                    )

                chunks_folder.rmdir()

            except Exception:
                traceback.print_exc()

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
            print("=" * 80)

            return {
                **result,
                "status": "ASSEMBLY_COMPLETED",
                "manifest_path": str(
                    manifest_path,
                ),
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
    # RECOVER EXISTING ASSEMBLED FILE
    #
    # Useful for the job that already reached:
    #
    # FINAL FILE
    # SIZE
    #
    # but never created manifest.json.
    #
    # NO Excel inspection.
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

        if not job_folder.exists():
            raise FileNotFoundError(
                f"Job folder not found: "
                f"{job_folder}",
            )

        destination = (
            job_folder
            / safe_filename
        )

        if not destination.exists():
            raise FileNotFoundError(
                f"Final file not found: "
                f"{destination}",
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
        }

        result = await cls._finalize_job(
            job_id=job_id,
            job_folder=job_folder,
            uploaded=[
                metadata,
            ],
        )

        manifest_path = (
            job_folder
            / "manifest.json"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest was not created: "
                f"{manifest_path}",
            )

        return {
            **result,
            "status": "ASSEMBLY_COMPLETED",
            "manifest_path": str(
                manifest_path,
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
            ) not in (
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