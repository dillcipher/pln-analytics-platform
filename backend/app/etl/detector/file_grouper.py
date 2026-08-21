from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

from app.core.constants import RAW_UPLOAD
from app.etl.detector.detector import FileDetector


class FileGrouper:
    """Group uploaded files by dataset and business month.

    The manifest is a cache of detection results. When a previous job has a
    stale/unknown dataset, the actual workbook is inspected through
    FileDetector so generic filenames such as ``test.xlsx`` can still be
    recovered safely.
    """

    KNOWN_DATASETS = {
        FileDetector.ANEV,
        FileDetector.DLPD_PASCABAYAR,
        FileDetector.DLPD_PRABAYAR,
        FileDetector.PENGECEKAN,
        FileDetector.CUSTOMER_LOCATION,
    }

    @staticmethod
    def _normalize_dataset(value) -> str | None:
        if value is None:
            return None

        normalized = (
            str(value)
            .strip()
            .upper()
            .replace("-", "_")
            .replace(" ", "_")
        )

        aliases = {
            "DLPD_PRA": FileDetector.DLPD_PRABAYAR,
            "DLPD_PRABAYAR": FileDetector.DLPD_PRABAYAR,
            "PRABAYAR": FileDetector.DLPD_PRABAYAR,
            "DLPD_PASCA": FileDetector.DLPD_PASCABAYAR,
            "DLPD_PASCABAYAR": FileDetector.DLPD_PASCABAYAR,
            "PASCABAYAR": FileDetector.DLPD_PASCABAYAR,
            "PENGECEK": FileDetector.PENGECEKAN,
            "PENGECEKAN": FileDetector.PENGECEKAN,
            "CUSTOMER_LOCATION": FileDetector.CUSTOMER_LOCATION,
            "CUSTOMERLOCATION": FileDetector.CUSTOMER_LOCATION,
            "DIL": FileDetector.CUSTOMER_LOCATION,
        }

        return aliases.get(normalized, normalized or None)

    @staticmethod
    def _find_uploaded_file(filename: str) -> Path | None:
        """Find a legacy assembled file when the caller has no job_folder.

        Older ETL jobs call ``group(manifest[\"files\"])`` without passing the
        job directory. Search the durable incoming tree so those jobs can be
        reclassified after a deployment instead of being permanently stuck
        with dataset=None.
        """
        try:
            candidates = [
                path
                for path in RAW_UPLOAD.glob(f"*/{Path(filename).name}")
                if path.is_file()
            ]
        except Exception:
            return None

        if not candidates:
            return None

        return max(candidates, key=lambda path: path.stat().st_mtime_ns)

    @classmethod
    def _resolve_dataset(
        cls,
        file: dict,
        job_folder: Path | None = None,
    ) -> str | None:
        filename = file.get("filename") or file.get("name")
        manifest_dataset = cls._normalize_dataset(file.get("dataset"))

        if filename:
            try:
                detected = FileDetector.detect(Path(str(filename)))
            except Exception:
                detected = FileDetector.UNKNOWN

            if detected in cls.KNOWN_DATASETS:
                return detected

        # Prefer the current job folder when supplied.
        actual_path = None
        if filename and job_folder is not None:
            candidate = job_folder / str(filename)
            if candidate.exists():
                actual_path = candidate

        # Legacy recovery: older orchestrator versions did not pass the job
        # folder into FileGrouper. Find the assembled workbook on disk.
        if actual_path is None and filename:
            actual_path = cls._find_uploaded_file(str(filename))

        if actual_path is not None:
            try:
                detected = FileDetector.detect(actual_path)
            except Exception:
                detected = FileDetector.UNKNOWN

            if detected in cls.KNOWN_DATASETS:
                return detected

        if manifest_dataset in cls.KNOWN_DATASETS:
            return manifest_dataset

        return None

    @classmethod
    def group(
        cls,
        files: list[dict],
        job_folder: Path | None = None,
    ) -> dict[tuple[str | None, str | None], list[dict]]:
        grouped: DefaultDict[
            tuple[str | None, str | None],
            list[dict],
        ] = defaultdict(list)

        unknown_files: list[str] = []

        for file in files:
            record = dict(file)
            dataset = cls._resolve_dataset(record, job_folder=job_folder)
            month = record.get("month")

            if dataset is None:
                unknown_files.append(
                    str(record.get("filename") or record.get("name") or "<unknown>")
                )
                continue

            record["dataset"] = dataset
            grouped[(dataset, month)].append(record)

        if unknown_files:
            raise ValueError(
                "Unable to detect dataset for uploaded file(s): "
                + ", ".join(unknown_files)
                + ". Use a supported PLN dataset or upload a valid Excel workbook."
            )

        return dict(grouped)
