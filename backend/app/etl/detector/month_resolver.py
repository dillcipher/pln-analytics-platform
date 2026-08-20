from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app.etl.detector.detector import FileDetector
from app.etl.validator.validator import DatasetValidator


class MonthResolver:
    """
    Resolve business month information for an input file.

    IMPORTANT
    ---------
    DLPD is NOT assumed to contain only one business month.

    A single DLPD Excel file may contain records belonging to
    multiple months.

    For DLPD, the business month is resolved per row using:

        THBL
          ↓
      DLPD_TGLBACA
          ↓
       THBLREK

    THBL and THBLREK are source/reference period fields and are
    never overwritten.

    Coordinate master files remain monthless.

    No month is inferred from:
    - JOB folder
    - upload timestamp
    - filesystem timestamp
    - current date
    """

    # ==========================================================
    # CONSTANTS
    # ==========================================================

    MONTH_PATTERN = re.compile(
        r"^(20\d{2})(0[1-9]|1[0-2])$"
    )

    MONTH_SEARCH_PATTERN = re.compile(
        r"(20\d{2})(0[1-9]|1[0-2])"
    )

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    # ==========================================================
    # FILENAME
    # ==========================================================

    @staticmethod
    def _normalized_filename(
        filepath: Path,
    ) -> str:
        name = (
            Path(filepath)
            .name
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

    # ==========================================================
    # COORDINATE MASTER
    # ==========================================================

    @classmethod
    def is_coordinate_master(
        cls,
        filepath: Path,
    ) -> bool:

        if FileDetector.is_coordinate_master(
            filepath,
        ):
            return True

        return (
            cls._normalized_filename(
                filepath,
            )
            in cls.COORDINATE_MASTER_FILES
        )

    # ==========================================================
    # MONTH NORMALIZATION
    # ==========================================================

    @classmethod
    def _normalize_month(
        cls,
        value,
    ) -> str | None:
        """
        Normalize a value into YYYYMM.

        Examples:

            202601
            "202601"
            "2026-01"
            "2026/01"
            datetime(2026, 1, 1)

        Returns None for invalid values.
        """

        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except Exception:
            pass

        # ------------------------------------------------------
        # Pandas timestamp
        # ------------------------------------------------------

        if isinstance(
            value,
            pd.Timestamp,
        ):
            try:
                return value.strftime(
                    "%Y%m",
                )
            except Exception:
                return None

        # ------------------------------------------------------
        # Python datetime/date-like values
        # ------------------------------------------------------

        if hasattr(
            value,
            "year",
        ) and hasattr(
            value,
            "month",
        ):
            try:
                year = int(value.year)
                month = int(value.month)

                candidate = (
                    f"{year:04d}"
                    f"{month:02d}"
                )

                if cls.MONTH_PATTERN.fullmatch(
                    candidate,
                ):
                    return candidate

            except Exception:
                pass

        # ------------------------------------------------------
        # Numeric values
        # ------------------------------------------------------

        if isinstance(
            value,
            (int, float),
        ):
            try:
                numeric = int(value)

                text = str(numeric)

                if cls.MONTH_PATTERN.fullmatch(
                    text,
                ):
                    return text

            except Exception:
                pass

        # ------------------------------------------------------
        # String values
        # ------------------------------------------------------

        text = str(value).strip()

        if not text:
            return None

        # Direct YYYYMM
        if cls.MONTH_PATTERN.fullmatch(
            text,
        ):
            return text

        # Search YYYYMM inside strings
        match = cls.MONTH_SEARCH_PATTERN.search(
            text,
        )

        if match:
            return (
                f"{match.group(1)}"
                f"{match.group(2)}"
            )

        # Excel/date representation
        try:
            parsed = pd.to_datetime(
                text,
                errors="coerce",
            )

            if not pd.isna(parsed):
                candidate = parsed.strftime(
                    "%Y%m",
                )

                if cls.MONTH_PATTERN.fullmatch(
                    candidate,
                ):
                    return candidate

        except Exception:
            pass

        return None

    # ==========================================================
    # DATE NORMALIZATION
    # ==========================================================

    @staticmethod
    def _parse_date(
        value,
    ) -> pd.Timestamp | None:

        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except Exception:
            pass

        try:
            parsed = pd.to_datetime(
                value,
                errors="coerce",
            )

            if pd.isna(parsed):
                return None

            return pd.Timestamp(
                parsed,
            )

        except Exception:
            return None

    # ==========================================================
    # MONTH BOUNDARIES
    # ==========================================================

    @classmethod
    def _month_start(
        cls,
        value,
    ) -> pd.Timestamp | None:

        month = cls._normalize_month(
            value,
        )

        if not month:
            return None

        try:
            return pd.Timestamp(
                year=int(month[:4]),
                month=int(month[4:6]),
                day=1,
            )

        except Exception:
            return None

    @staticmethod
    def _month_end(
        value: pd.Timestamp | None,
    ) -> pd.Timestamp | None:

        if value is None:
            return None

        try:
            return (
                value
                + pd.offsets.MonthEnd(1)
                + pd.Timedelta(days=1)
                - pd.Timedelta(microseconds=1)
            )

        except Exception:
            return None

    # ==========================================================
    # SHEET
    # ==========================================================

    @classmethod
    def _get_sheet_name(
        cls,
        filepath: Path,
        dataset: str,
    ) -> str:
        return DatasetValidator.get_sheet_name(
            filepath,
            dataset,
        )

    # ==========================================================
    # READ DLPD MONTHS
    # ==========================================================

    @classmethod
    def _read_dlpd_months(
        cls,
        filepath: Path,
        dataset: str,
        sheet_name: str,
    ) -> list[str]:
        """
        Inspect ALL DLPD rows and determine all business months
        represented by the file.

        Required source fields:

            THBL
            THBLREK
            DLPD_TGLBACA

        The detailed date is used when it falls inside the
        THBL/THBLREK period.

        If the detailed date is unavailable, THBLREK and THBL
        are used as fallbacks.
        """

        try:
            header = DatasetValidator.detect_header_row(
                filepath=filepath,
                sheet_name=sheet_name,
            )

            dataframe = pd.read_excel(
                filepath,
                sheet_name=sheet_name,
                header=header,
                usecols=lambda column: (
                    DatasetValidator.normalize_column(
                        column,
                    )
                    in {
                        DatasetValidator.normalize_column(
                            "THBL",
                        ),
                        DatasetValidator.normalize_column(
                            "THBLREK",
                        ),
                        DatasetValidator.normalize_column(
                            "DLPD_TGLBACA",
                        ),
                    }
                ),
            )

            if dataframe.empty:
                return []

            dataframe.columns = [
                DatasetValidator.normalize_column(
                    column,
                )
                for column in dataframe.columns
            ]

            thbl_column = DatasetValidator.normalize_column(
                "THBL",
            )

            thblrek_column = DatasetValidator.normalize_column(
                "THBLREK",
            )

            date_column = DatasetValidator.normalize_column(
                "DLPD_TGLBACA",
            )

            # --------------------------------------------------
            # Ensure expected columns exist.
            # --------------------------------------------------

            for column in (
                thbl_column,
                thblrek_column,
                date_column,
            ):
                if column not in dataframe.columns:
                    dataframe[column] = None

            months: set[str] = set()

            # --------------------------------------------------
            # Resolve every row.
            # --------------------------------------------------

            for _, row in dataframe.iterrows():

                thbl = row.get(
                    thbl_column,
                )

                thblrek = row.get(
                    thblrek_column,
                )

                detail_date = row.get(
                    date_column,
                )

                thbl_start = cls._month_start(
                    thbl,
                )

                thblrek_start = cls._month_start(
                    thblrek,
                )

                parsed_date = cls._parse_date(
                    detail_date,
                )

                # ==================================================
                # PRIMARY RULE
                #
                # DLPD_TGLBACA determines the business month
                # when it lies inside THBL -> THBLREK.
                # ==================================================

                if (
                    parsed_date is not None
                    and thbl_start is not None
                    and thblrek_start is not None
                ):
                    period_start = min(
                        thbl_start,
                        thblrek_start,
                    )

                    period_month = max(
                        thbl_start,
                        thblrek_start,
                    )

                    period_end = cls._month_end(
                        period_month,
                    )

                    if (
                        period_end is not None
                        and period_start
                        <= parsed_date
                        <= period_end
                    ):
                        months.add(
                            parsed_date.strftime(
                                "%Y%m",
                            ),
                        )
                        continue

                # ==================================================
                # FALLBACK 1
                #
                # If only one boundary exists, use the detailed
                # date's month.
                # ==================================================

                if (
                    parsed_date is not None
                    and (
                        thbl_start is not None
                        or thblrek_start is not None
                    )
                ):
                    months.add(
                        parsed_date.strftime(
                            "%Y%m",
                        ),
                    )
                    continue

                # ==================================================
                # FALLBACK 2
                #
                # THBLREK
                # ==================================================

                month = cls._normalize_month(
                    thblrek,
                )

                if month:
                    months.add(
                        month,
                    )
                    continue

                # ==================================================
                # FALLBACK 3
                #
                # THBL
                # ==================================================

                month = cls._normalize_month(
                    thbl,
                )

                if month:
                    months.add(
                        month,
                    )

            return sorted(
                months,
            )

        except Exception as exc:
            print(
                "[MonthResolver] "
                f"{filepath.name}: {exc}"
            )
            return []

    # ==========================================================
    # LEGACY / SINGLE MONTH READER
    # ==========================================================

    @classmethod
    def _read_first_month(
        cls,
        filepath: Path,
        dataset: str,
        sheet_name: str,
        column_name: str,
    ) -> str | None:
        """
        Backward-compatible helper.

        IMPORTANT:
        This method no longer reads only the first row.

        It reads all values from the requested column and returns
        the first chronologically available valid month.

        New DLPD code should use resolve_months().
        """

        try:
            header = DatasetValidator.detect_header_row(
                filepath=filepath,
                sheet_name=sheet_name,
            )

            dataframe = pd.read_excel(
                filepath,
                sheet_name=sheet_name,
                header=header,
                usecols=lambda column: (
                    DatasetValidator.normalize_column(
                        column,
                    )
                    == DatasetValidator.normalize_column(
                        column_name,
                    )
                ),
            )

            if dataframe.empty:
                return None

            dataframe.columns = [
                DatasetValidator.normalize_column(
                    column,
                )
                for column in dataframe.columns
            ]

            normalized_column = (
                DatasetValidator.normalize_column(
                    column_name,
                )
            )

            if normalized_column not in dataframe.columns:
                return None

            months: set[str] = set()

            for value in dataframe[
                normalized_column
            ]:
                month = cls._normalize_month(
                    value,
                )

                if month:
                    months.add(
                        month,
                    )

            if not months:
                return None

            return sorted(
                months,
            )[0]

        except Exception as exc:
            print(
                "[MonthResolver] "
                f"{filepath.name}: {exc}"
            )
            return None

    # ==========================================================
    # FILENAME MONTH
    # ==========================================================

    @classmethod
    def _resolve_from_filename(
        cls,
        filepath: Path,
    ) -> str | None:

        match = cls.MONTH_SEARCH_PATTERN.search(
            filepath.stem,
        )

        if match:
            return (
                f"{match.group(1)}"
                f"{match.group(2)}"
            )

        return None

    # ==========================================================
    # RESOLVE ALL MONTHS
    # ==========================================================

    @classmethod
    def resolve_months(
        cls,
        filepath: Path,
    ) -> list[str]:

        filepath = Path(
            filepath,
        )

        dataset = FileDetector.detect(
            filepath,
        )

        # ======================================================
        # COORDINATE MASTER
        # ======================================================

        if cls.is_coordinate_master(
            filepath,
        ):
            return []

        # ======================================================
        # ANEV
        # ======================================================

        if dataset == FileDetector.ANEV:
            month = cls._resolve_from_filename(
                filepath,
            )

            return (
                [month]
                if month
                else []
            )

        # ======================================================
        # CUSTOMER LOCATION / DIL
        # ======================================================

        if dataset == FileDetector.CUSTOMER_LOCATION:
            month = cls._resolve_from_filename(
                filepath,
            )

            return (
                [month]
                if month
                else []
            )

        # ======================================================
        # DLPD PASCABAYAR
        # ======================================================

        if dataset == FileDetector.DLPD_PASCABAYAR:
            return cls._read_dlpd_months(
                filepath=filepath,
                dataset=dataset,
                sheet_name=cls._get_sheet_name(
                    filepath,
                    dataset,
                ),
            )

        # ======================================================
        # DLPD PRABAYAR
        # ======================================================

        if dataset == FileDetector.DLPD_PRABAYAR:
            return cls._read_dlpd_months(
                filepath=filepath,
                dataset=dataset,
                sheet_name=cls._get_sheet_name(
                    filepath,
                    dataset,
                ),
            )

        # ======================================================
        # PENGECEKAN
        # ======================================================

        if dataset == FileDetector.PENGECEKAN:
            return []

        return []

    # ==========================================================
    # RESOLVE SINGLE MONTH - BACKWARD COMPATIBILITY
    # ==========================================================

    @classmethod
    def resolve(
        cls,
        filepath: Path,
    ) -> str | None:
        """
        Backward-compatible single-month API.

        If a file contains exactly one month, return that month.

        If a DLPD file contains MULTIPLE months, return None.

        The multi-month case MUST be handled through:

            MonthResolver.resolve_months(filepath)

        This prevents the old behavior where the first row
        incorrectly represented the entire file.
        """

        months = cls.resolve_months(
            filepath,
        )

        if len(months) == 1:
            return months[0]

        return None