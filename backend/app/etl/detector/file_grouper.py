from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict

from app.etl.detector.detector import FileDetector


class FileGrouper:
    """
    Group uploaded files by dataset and business month.

    The manifest is treated as a cache of detection results, not the
    ultimate source of truth. Older jobs can contain missing, stale, or
    differently-cased dataset values. Re-detecting from the filename here
    makes ETL recovery safe without requiring another upload.

    Coordinate masters
    ------------------
    TO_PRABAYAR.xlsx and TO_PASCABAYAR.xlsx are intentionally
    monthless. They therefore form a CUSTOMER_LOCATION/None group.

    No month is inferred or changed here. MonthResolver remains the
    single source of truth for month resolution.
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

        normalized = str(value).strip().upper().replace("-", "_").replace(" ", "_")

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

    @classmethod
    def _resolve_dataset(cls, file: dict) -> str | None:
        filename = file.get("filename") or file.get("name")
        manifest_dataset = cls._normalize_dataset(file.get("dataset"))

        # Filename detection is authoritative whenever it recognizes a
        # supported dataset. This repairs stale manifests from previous
        # upload/assembly implementations during retry/recovery.
        if filename:
            try:
                detected = FileDetector.detect(__import__("pathlib").Path(str(filename)))
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
    ) -> dict[tuple[str | None, str | None], list[dict]]:
        grouped: DefaultDict[
            tuple[str | None, str | None],
            list[dict],
        ] = defaultdict(list)

        for file in files:
            record = dict(file)
            dataset = cls._resolve_dataset(record)
            month = record.get("month")

            # Keep the normalized dataset in the record so every downstream
            # ETL stage sees the repaired classification.
            record["dataset"] = dataset

            key = (dataset, month)
            grouped[key].append(record)

        return dict(grouped)
