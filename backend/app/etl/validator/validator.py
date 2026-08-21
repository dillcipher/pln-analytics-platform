from __future__ import annotations

import re
import os
import time
import zipfile
from pathlib import Path

import pandas as pd


class DatasetValidator:
    """
    Validate uploaded PLN datasets.

    CUSTOMER_LOCATION supports two coordinate schemas:

    1. Existing DIL schema:
       IDPEL + KOORDINAT_X + KOORDINAT_Y

    2. Fixed TO coordinate-master schema:
       IDPEL + LATITUDE + LONGITUDE

    The TO schema is accepted before transformation because
    CustomerLocationTransformer maps LATITUDE/LONGITUDE into the
    canonical KOORDINAT_X/KOORDINAT_Y representation.
    """

    REQUIRED_COLUMNS = {
        "ANEV": ["LOCATION_CODE", "READ_DATE", "SUSPECT_NAME"],
        "DLPD_PASCABAYAR": ["IDPEL", "THBLREK", "DLPD"],
        "DLPD_PRABAYAR": ["IDPEL", "THBL"],
        "PENGECEKAN": ["IDPEL", "NAMA"],
        "CUSTOMER_LOCATION": ["IDPEL", "KOORDINAT_X", "KOORDINAT_Y"],
    }

    CUSTOMER_LOCATION_COORDINATE_SCHEMAS = (
        ("KOORDINAT_X", "KOORDINAT_Y"),
        ("LATITUDE", "LONGITUDE"),
    )

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    SHEET_PRIORITY = {
        "ANEV": ["ANEV", "ANNEV", "SHEET1"],
        "DLPD_PASCABAYAR": ["MAIN", "SHEET1"],
        "DLPD_PRABAYAR": ["SHEET1", "MAIN"],
        "PENGECEKAN": ["DATA", "SHEET1"],
        "CUSTOMER_LOCATION": ["SHEET1", "DATA", "MAIN"],
    }

    @staticmethod
    def normalize_column(column: object) -> str:
        text = str(column).replace("\n", " ").upper()
        return re.sub(r"[^A-Z0-9]", "", text)

    @classmethod
    def _normalized_filename(cls, filepath: Path) -> str:
        name = filepath.name.lower().strip().replace("-", "_").replace(" ", "_")
        while "__" in name:
            name = name.replace("__", "_")
        return name

    @classmethod
    def is_coordinate_master(cls, filepath: Path) -> bool:
        return cls._normalized_filename(filepath) in cls.COORDINATE_MASTER_FILES

    @staticmethod
    def _is_chunk_assembled_path(filepath: Path) -> bool:
        """Return True for files in the durable incoming job tree."""
        try:
            resolved = os.path.abspath(os.fspath(filepath))
        except (TypeError, ValueError, OSError):
            return False
        markers = (
            os.path.normpath("/app/data/raw/incoming"),
            os.path.normpath("data/raw/incoming"),
        )
        return any(resolved == marker or resolved.startswith(marker + os.sep) for marker in markers)

    @classmethod
    def _wait_until_excel_is_valid(cls, filepath: Path) -> None:
        """Block validation while a recovered chunked Excel file is still assembling.

        Recovery can start ETL while the background chunk assembler is still
        writing the final filename. Pandas then sees a partial XLSX ZIP and
        raises BadZipFile. Synchronize at the validation boundary instead of
        consuming an incomplete workbook and triggering a false ETL retry.
        """
        filepath = Path(filepath)
        suffix = filepath.suffix.lower()
        if suffix not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
            return
        if not cls._is_chunk_assembled_path(filepath):
            return

        timeout = float(os.getenv("EXCEL_ASSEMBLY_WAIT_SECONDS", "300"))
        deadline = time.monotonic() + timeout
        last_signature = None
        stable_since = None

        while time.monotonic() < deadline:
            try:
                stat = filepath.stat()
            except FileNotFoundError:
                time.sleep(0.5)
                continue

            signature = (stat.st_size, stat.st_mtime_ns)
            if signature != last_signature:
                last_signature = signature
                stable_since = time.monotonic()
                time.sleep(0.5)
                continue

            if stable_since is None or time.monotonic() - stable_since < 1.0:
                time.sleep(0.25)
                continue

            try:
                with zipfile.ZipFile(filepath, "r") as archive:
                    if archive.testzip() is None:
                        return
            except (zipfile.BadZipFile, OSError):
                pass

            # File may still be growing or may have been exposed before the
            # assembler finished. Give it time to become a complete ZIP.
            time.sleep(0.75)

        raise RuntimeError(
            f"Excel assembly did not become a valid workbook within {timeout:.0f}s: {filepath}"
        )

    @classmethod
    def get_sheet_name(cls, filepath: Path, dataset: str) -> str:
        filepath = Path(filepath)
        cls._wait_until_excel_is_valid(filepath)

        excel = pd.ExcelFile(filepath)
        sheets = {str(sheet).strip().upper(): sheet for sheet in excel.sheet_names}
        priorities = cls.SHEET_PRIORITY.get(dataset, [])

        for sheet in priorities:
            normalized = str(sheet).strip().upper()
            if normalized in sheets:
                return sheets[normalized]

        if not excel.sheet_names:
            raise ValueError(f"No worksheet found in '{filepath.name}'.")
        return excel.sheet_names[0]

    @classmethod
    def detect_header_row(cls, filepath: Path, sheet_name: str) -> int:
        cls._wait_until_excel_is_valid(Path(filepath))
        preview = pd.read_excel(filepath, sheet_name=sheet_name, header=None, nrows=15)
        for index, row in preview.iterrows():
            values = [cls.normalize_column(col) for col in row.tolist()]
            if "IDPEL" in values or "LOCATIONCODE" in values:
                return int(index)
        return 0

    @classmethod
    def _read_normalized_columns(cls, filepath: Path, dataset: str) -> list[str]:
        sheet = cls.get_sheet_name(filepath, dataset)
        header = cls.detect_header_row(filepath, sheet)
        df = pd.read_excel(filepath, sheet_name=sheet, header=header, nrows=5)
        return [cls.normalize_column(col) for col in df.columns]

    @classmethod
    def _validate_customer_location(cls, columns: list[str]) -> dict:
        normalized_idpel = cls.normalize_column("IDPEL")
        missing: list[str] = []
        if normalized_idpel not in columns:
            missing.append("IDPEL")

        coordinate_schema_found = False
        for latitude, longitude in cls.CUSTOMER_LOCATION_COORDINATE_SCHEMAS:
            latitude_column = cls.normalize_column(latitude)
            longitude_column = cls.normalize_column(longitude)
            if latitude_column in columns and longitude_column in columns:
                coordinate_schema_found = True
                break

        if not coordinate_schema_found:
            missing.append("LATITUDE/LONGITUDE or KOORDINAT_X/KOORDINAT_Y")

        return {
            "status": "PASSED" if not missing else "FAILED",
            "missing_columns": missing,
        }

    @classmethod
    def validate(cls, filepath: Path, dataset: str) -> dict:
        filepath = Path(filepath)
        if not filepath.exists():
            return {"status": "FAILED", "missing_columns": [], "error": f"File not found: {filepath}"}
        if dataset not in cls.REQUIRED_COLUMNS:
            return {"status": "UNKNOWN", "missing_columns": []}

        try:
            columns = cls._read_normalized_columns(filepath=filepath, dataset=dataset)
        except Exception as exc:
            return {"status": "FAILED", "missing_columns": [], "error": str(exc)}

        if dataset == "CUSTOMER_LOCATION":
            return cls._validate_customer_location(columns)

        required = [cls.normalize_column(col) for col in cls.REQUIRED_COLUMNS[dataset]]
        missing = [col for col in required if col not in columns]
        return {"status": "PASSED" if not missing else "FAILED", "missing_columns": missing}
