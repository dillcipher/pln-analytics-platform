from __future__ import annotations

import json
import traceback
from datetime import datetime

import aiofiles
from fastapi import UploadFile

from app.application.jobs.job_manager import JobManager
from app.application.jobs.job_status import JobStatus
from app.core.constants import RAW_UPLOAD
from app.etl.detector.detector import FileDetector
from app.etl.detector.month_resolver import MonthResolver
from app.etl.validator.validator import DatasetValidator


UPLOAD_FOLDER = RAW_UPLOAD


class UploadService:
    """
    Upload Engine

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

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        name = filename.lower().strip()
        name = name.replace("-", "_").replace(" ", "_")

        while "__" in name:
            name = name.replace("__", "_")

        return name

    @classmethod
    def _is_coordinate_master(cls, filename: str) -> bool:
        return (
            cls._normalize_filename(filename)
            in cls.COORDINATE_MASTER_FILES
        )

    @staticmethod
    async def save_files(files: list[UploadFile]):
        print("=" * 80)
        print("UPLOAD START")

        job_id = datetime.now().strftime(
            "JOB_%Y%m%d_%H%M%S"
        )

        job_folder = UPLOAD_FOLDER / job_id
        job_folder.mkdir(parents=True, exist_ok=True)

        uploaded: list[dict] = []

        for file in files:
            print()
            print(f"Processing : {file.filename}")

            original_filename = file.filename or "uploaded_file"

            # Prevent client-supplied path components from escaping
            # the generated job folder.
            safe_filename = (
                original_filename.replace("\\", "/")
                .split("/")[-1]
            )

            if not safe_filename:
                safe_filename = "uploaded_file"

            destination = job_folder / safe_filename

            async with aiofiles.open(destination, "wb") as out:
                while chunk := await file.read(1024 * 1024):
                    await out.write(chunk)

            print("✓ Saved")
            print("✓ File Path :", destination)

            dataset = None
            month = None
            validation = {
                "status": "FAILED",
                "missing_columns": [],
            }

            try:
                dataset = FileDetector.detect(destination)

                if dataset == FileDetector.UNKNOWN:
                    validation = {
                        "status": "FAILED",
                        "missing_columns": [],
                        "error": (
                            "Unable to detect dataset from filename."
                        ),
                    }
                else:
                    month = MonthResolver.resolve(destination)

                    validation = DatasetValidator.validate(
                        destination,
                        dataset,
                    )

                print("✓ Dataset :", dataset)
                print("✓ Month :", month)
                print("✓ Validation :", validation["status"])

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
                UploadService._is_coordinate_master(
                    safe_filename
                )
            )

            if is_coordinate_master:
                print(
                    "✓ Coordinate Master :",
                    safe_filename,
                )

                # Coordinate masters are deliberately monthless.
                month = None

                # Keep the manifest invariant even if detector logic
                # is changed in the future.
                if dataset == FileDetector.UNKNOWN:
                    dataset = FileDetector.CUSTOMER_LOCATION

            uploaded.append(
                {
                    "filename": safe_filename,
                    "original_filename": original_filename,
                    "size": destination.stat().st_size,
                    "content_type": file.content_type,
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
            )

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

        manifest_path = job_folder / "manifest.json"

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
            if item.get("is_coordinate_master")
        ]

        failed_files = [
            item["filename"]
            for item in uploaded
            if item.get("validation") != "PASSED"
        ]

        print()
        print("Manifest :")
        print(manifest_path)
        print()
        print("Coordinate Masters :", coordinate_masters)
        print("Validation Failures :", failed_files)
        print()
        print("UPLOAD FINISHED")
        print("=" * 80)

        return {
            "success": True,
            "job_id": job_id,
            "uploaded_at": manifest["uploaded_at"],
            "total_files": len(uploaded),
            "files": uploaded,
        }