from __future__ import annotations

import re
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

    # ==========================================================
    # REQUIRED COLUMNS
    # ==========================================================

    REQUIRED_COLUMNS = {
        "ANEV": [
            "LOCATION_CODE",
            "READ_DATE",
            "SUSPECT_NAME",
        ],
        "DLPD_PASCABAYAR": [
            "IDPEL",
            "THBLREK",
            "DLPD",
        ],
        "DLPD_PRABAYAR": [
            "IDPEL",
            "THBL",
        ],
        "PENGECEKAN": [
            "IDPEL",
            "NAMA",
        ],
        "CUSTOMER_LOCATION": [
            "IDPEL",
            "KOORDINAT_X",
            "KOORDINAT_Y",
        ],
    }

    # ==========================================================
    # ALTERNATIVE COORDINATE SCHEMAS
    # ==========================================================

    CUSTOMER_LOCATION_COORDINATE_SCHEMAS = (
        ("KOORDINAT_X", "KOORDINAT_Y"),
        ("LATITUDE", "LONGITUDE"),
    )

    # ==========================================================
    # FIXED COORDINATE MASTER FILES
    # ==========================================================

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    # ==========================================================
    # SHEET PRIORITY
    # ==========================================================

    SHEET_PRIORITY = {
        "ANEV": [
            "ANEV",
            "ANNEV",
            "SHEET1",
        ],
        "DLPD_PASCABAYAR": [
            "MAIN",
            "SHEET1",
        ],
        "DLPD_PRABAYAR": [
            "SHEET1",
            "MAIN",
        ],
        "PENGECEKAN": [
            "DATA",
            "SHEET1",
        ],
        "CUSTOMER_LOCATION": [
            "SHEET1",
            "DATA",
            "MAIN",
        ],
    }

    # ==========================================================
    # COLUMN NORMALIZATION
    # ==========================================================

    @staticmethod
    def normalize_column(
        column: object,
    ) -> str:
        """
        Normalize Excel column names.

        Examples:
            'IDPEL'       -> 'IDPEL'
            'ID PEL'      -> 'IDPEL'
            'LATITUDE'    -> 'LATITUDE'
            'KOORDINAT X' -> 'KOORDINATX'
        """

        text = str(column)

        text = text.replace(
            "\n",
            " ",
        )

        text = text.upper()

        text = re.sub(
            r"[^A-Z0-9]",
            "",
            text,
        )

        return text

    # ==========================================================
    # FILENAME NORMALIZATION
    # ==========================================================

    @classmethod
    def _normalized_filename(
        cls,
        filepath: Path,
    ) -> str:
        name = filepath.name.lower().strip()

        name = name.replace(
            "-",
            "_",
        )

        name = name.replace(
            " ",
            "_",
        )

        while "__" in name:
            name = name.replace(
                "__",
                "_",
            )

        return name

    @classmethod
    def is_coordinate_master(
        cls,
        filepath: Path,
    ) -> bool:
        """
        Return True for the fixed TO coordinate master files.

        This helper is intentionally independent from dataset
        detection so the detector can use the same authoritative
        definition later.
        """

        return (
            cls._normalized_filename(filepath)
            in cls.COORDINATE_MASTER_FILES
        )

    # ==========================================================
    # SHEET
    # ==========================================================

    @classmethod
    def get_sheet_name(
        cls,
        filepath: Path,
        dataset: str,
    ) -> str:

        excel = pd.ExcelFile(
            filepath,
        )

        sheets = {
            str(sheet).strip().upper(): sheet
            for sheet in excel.sheet_names
        }

        priorities = cls.SHEET_PRIORITY.get(
            dataset,
            [],
        )

        for sheet in priorities:
            normalized = str(sheet).strip().upper()

            if normalized in sheets:
                return sheets[normalized]

        if not excel.sheet_names:
            raise ValueError(
                f"No worksheet found in '{filepath.name}'."
            )

        return excel.sheet_names[0]

    # ==========================================================
    # HEADER
    # ==========================================================

    @classmethod
    def detect_header_row(
        cls,
        filepath: Path,
        sheet_name: str,
    ) -> int:
        """
        Detect the header row automatically.

        A valid PLN dataset normally exposes IDPEL or LOCATION_CODE
        in its header. This also works for TO coordinate masters.
        """

        preview = pd.read_excel(
            filepath,
            sheet_name=sheet_name,
            header=None,
            nrows=15,
        )

        for index, row in preview.iterrows():

            values = [
                cls.normalize_column(col)
                for col in row.tolist()
            ]

            if (
                "IDPEL" in values
                or "LOCATIONCODE" in values
            ):
                return int(index)

        return 0

    # ==========================================================
    # READ COLUMNS
    # ==========================================================

    @classmethod
    def _read_normalized_columns(
        cls,
        filepath: Path,
        dataset: str,
    ) -> list[str]:

        sheet = cls.get_sheet_name(
            filepath,
            dataset,
        )

        header = cls.detect_header_row(
            filepath,
            sheet,
        )

        df = pd.read_excel(
            filepath,
            sheet_name=sheet,
            header=header,
            nrows=5,
        )

        return [
            cls.normalize_column(col)
            for col in df.columns
        ]

    # ==========================================================
    # CUSTOMER LOCATION VALIDATION
    # ==========================================================

    @classmethod
    def _validate_customer_location(
        cls,
        columns: list[str],
    ) -> dict:
        """
        Validate either the existing DIL coordinate schema or
        the fixed TO coordinate-master schema.
        """

        normalized_idpel = cls.normalize_column(
            "IDPEL",
        )

        missing: list[str] = []

        if normalized_idpel not in columns:
            missing.append("IDPEL")

        coordinate_schema_found = False

        for latitude, longitude in (
            cls.CUSTOMER_LOCATION_COORDINATE_SCHEMAS
        ):
            latitude_column = cls.normalize_column(
                latitude,
            )

            longitude_column = cls.normalize_column(
                longitude,
            )

            if (
                latitude_column in columns
                and longitude_column in columns
            ):
                coordinate_schema_found = True
                break

        if not coordinate_schema_found:
            missing.append(
                "LATITUDE/LONGITUDE or "
                "KOORDINAT_X/KOORDINAT_Y"
            )

        return {
            "status": (
                "PASSED"
                if not missing
                else "FAILED"
            ),
            "missing_columns": missing,
        }

    # ==========================================================
    # VALIDATE
    # ==========================================================

    @classmethod
    def validate(
        cls,
        filepath: Path,
        dataset: str,
    ) -> dict:

        filepath = Path(filepath)

        if not filepath.exists():
            return {
                "status": "FAILED",
                "missing_columns": [],
                "error": (
                    f"File not found: {filepath}"
                ),
            }

        if dataset not in cls.REQUIRED_COLUMNS:
            return {
                "status": "UNKNOWN",
                "missing_columns": [],
            }

        try:

            columns = cls._read_normalized_columns(
                filepath=filepath,
                dataset=dataset,
            )

        except Exception as exc:

            return {
                "status": "FAILED",
                "missing_columns": [],
                "error": str(exc),
            }

        # ======================================================
        # CUSTOMER LOCATION
        # ======================================================

        if dataset == "CUSTOMER_LOCATION":

            return cls._validate_customer_location(
                columns,
            )

        # ======================================================
        # STANDARD DATASET VALIDATION
        # ======================================================

        required = [
            cls.normalize_column(col)
            for col in cls.REQUIRED_COLUMNS[
                dataset
            ]
        ]

        missing = [
            col
            for col in required
            if col not in columns
        ]

        return {
            "status": (
                "PASSED"
                if not missing
                else "FAILED"
            ),
            "missing_columns": missing,
        }