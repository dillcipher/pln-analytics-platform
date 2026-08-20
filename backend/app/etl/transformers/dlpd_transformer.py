from __future__ import annotations

import re

import pandas as pd

from app.etl.transformers.base_transformer import BaseTransformer


class DLPDTransformer(BaseTransformer):
    """
    DLPD dataset transformer.

    MONTH is resolved per row.

    Business rule
    -------------
    A DLPD record contains a period bounded by THBL and THBLREK.
    The detailed inspection/reading date (DLPD_TGLBACA) is used
    to determine the actual business month for that row.

    Example:

        THBL        = 202605
        THBLREK     = 202606
        DLPD_TGLBACA = 2026-06-15

    Result:

        MONTH = 202606

    THBL and THBLREK remain untouched as source/reference fields.
    """

    # ==========================================================
    # STRING COLUMNS
    # ==========================================================

    STRING_COLUMNS = [
        "IDPEL",
        "NAMA",
        "ALAMAT",
        "NOBANG",
        "KETNOBANG",
        "KDGARDU",
        "NAMAGARDU",
        "KDDK",
        "UNITUPI",
        "UNITAP",
        "UNITUP",
        "TARIF",
        "SEGMENT",
        "KDPT",
        "KDPT_2",
        "THBL",
        "THBLREK",
        "MONTH",
        "DATASET",

        "DLPD",
        "DLPD_LM",
        "DLPD_FKM",
        "DLPD_KVARH",
        "DLPD_3BLN",
        "DLPD_JNSMUTASI",
    ]

    # ==========================================================
    # NUMERIC COLUMNS
    # ==========================================================

    NUMERIC_COLUMNS = [
        "DAYA",
        "RPPTL",
        "RPTB",
        "RPPPN",
        "RPBPJU",
        "RPBK1",
        "RPBK2",
        "RPBK3",
        "RPTAG",
        "KWHLWBP",
        "KWHWBP",
        "BLOK3",
    ]

    # ==========================================================
    # DATE COLUMNS
    # ==========================================================

    DATE_COLUMNS = [
        "DLPD_TGLBACA",
        "TGLCABUTPASANG",
    ]

    # ==========================================================
    # MONTH HELPERS
    # ==========================================================

    @staticmethod
    def _normalize_month_value(
        value,
    ) -> str | None:
        """
        Normalize a month-like value to YYYYMM.

        Supported examples:

            202606
            "202606"
            "2026-06"
            "2026/06"
            datetime(2026, 6, 1)
            "2026-06-15"

        Returns None when the value cannot safely be interpreted
        as a valid YYYYMM value.
        """

        if value is None:
            return None

        if pd.isna(value):
            return None

        # ------------------------------------------------------
        # Datetime
        # ------------------------------------------------------

        if isinstance(
            value,
            (
                pd.Timestamp,
                pd.DatetimeIndex,
            ),
        ):
            try:
                if isinstance(value, pd.Timestamp):
                    return value.strftime("%Y%m")
            except Exception:
                return None

        # ------------------------------------------------------
        # Numeric YYYYMM
        # ------------------------------------------------------

        if isinstance(value, (int, float)):
            try:
                if pd.isna(value):
                    return None

                numeric = int(value)

                text = str(numeric)

                if re.fullmatch(
                    r"20\d{4}",
                    text,
                ):
                    month = int(text[4:6])

                    if 1 <= month <= 12:
                        return text

            except Exception:
                pass

        # ------------------------------------------------------
        # String
        # ------------------------------------------------------

        text = str(value).strip()

        if not text:
            return None

        # Direct YYYYMM
        match = re.search(
            r"(20\d{2})(0[1-9]|1[0-2])",
            text,
        )

        if match:
            return (
                f"{match.group(1)}"
                f"{match.group(2)}"
            )

        # Date-like value
        try:
            parsed = pd.to_datetime(
                text,
                errors="coerce",
            )

            if not pd.isna(parsed):
                return parsed.strftime("%Y%m")

        except Exception:
            pass

        return None

    @classmethod
    def _month_start(
        cls,
        value,
    ) -> pd.Timestamp | None:
        """
        Convert THBL/THBLREK-like value to the first day
        of its month.
        """

        month = cls._normalize_month_value(value)

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
        month_start: pd.Timestamp | None,
    ) -> pd.Timestamp | None:
        """
        Return the last moment of the month represented by
        month_start.
        """

        if month_start is None:
            return None

        try:
            return (
                month_start
                + pd.offsets.MonthEnd(1)
                + pd.Timedelta(days=1)
                - pd.Timedelta(microseconds=1)
            )

        except Exception:
            return None

    @classmethod
    def _resolve_row_month(
        cls,
        row: pd.Series,
    ) -> str | None:
        """
        Resolve MONTH for a single DLPD row.

        Primary rule
        ------------
        Use DLPD_TGLBACA as the detailed date.

        THBL and THBLREK define the valid period boundary.

        If DLPD_TGLBACA falls inside the THBL/THBLREK interval,
        its YYYYMM becomes MONTH.

        Fallback
        --------
        If the detailed date is unavailable or cannot be placed
        inside the interval, use the existing MONTH value if it
        is valid.

        As a final fallback, use THBLREK and then THBL.

        This prevents MONTH from becoming blank for otherwise
        usable DLPD records.
        """

        # ------------------------------------------------------
        # Read source values
        # ------------------------------------------------------

        thbl = row.get("THBL")

        thblrek = row.get("THBLREK")

        detail_date = row.get(
            "DLPD_TGLBACA",
        )

        existing_month = row.get(
            "MONTH",
        )

        # ------------------------------------------------------
        # Normalize boundaries
        # ------------------------------------------------------

        thbl_start = cls._month_start(
            thbl,
        )

        thblrek_start = cls._month_start(
            thblrek,
        )

        # ------------------------------------------------------
        # Detailed date
        # ------------------------------------------------------

        parsed_date = pd.to_datetime(
            detail_date,
            errors="coerce",
        )

        if not pd.isna(parsed_date):

            # --------------------------------------------------
            # If both THBL and THBLREK exist, construct the
            # inclusive period between the two month boundaries.
            # --------------------------------------------------

            if (
                thbl_start is not None
                and thblrek_start is not None
            ):
                period_start = min(
                    thbl_start,
                    thblrek_start,
                )

                period_end = cls._month_end(
                    max(
                        thbl_start,
                        thblrek_start,
                    ),
                )

                if (
                    period_end is not None
                    and period_start
                    <= parsed_date
                    <= period_end
                ):
                    return parsed_date.strftime(
                        "%Y%m",
                    )

            # --------------------------------------------------
            # If only one boundary is available, the detailed
            # date itself remains the best row-level month.
            # --------------------------------------------------

            elif (
                thbl_start is not None
                or thblrek_start is not None
            ):
                return parsed_date.strftime(
                    "%Y%m",
                )

        # ------------------------------------------------------
        # Existing MONTH fallback
        # ------------------------------------------------------

        normalized_existing = (
            cls._normalize_month_value(
                existing_month,
            )
        )

        if normalized_existing:
            return normalized_existing

        # ------------------------------------------------------
        # THBLREK fallback
        # ------------------------------------------------------

        normalized_thblrek = (
            cls._normalize_month_value(
                thblrek,
            )
        )

        if normalized_thblrek:
            return normalized_thblrek

        # ------------------------------------------------------
        # THBL fallback
        # ------------------------------------------------------

        normalized_thbl = (
            cls._normalize_month_value(
                thbl,
            )
        )

        if normalized_thbl:
            return normalized_thbl

        return None

    @classmethod
    def _resolve_month_per_row(
        cls,
        dataframe: pd.DataFrame,
    ) -> pd.Series:
        """
        Resolve MONTH independently for every DLPD record.
        """

        required_columns = {
            "THBL",
            "THBLREK",
            "DLPD_TGLBACA",
        }

        available = set(
            dataframe.columns,
        )

        # ------------------------------------------------------
        # Full business-rule path
        # ------------------------------------------------------

        if required_columns.issubset(
            available,
        ):
            return dataframe.apply(
                cls._resolve_row_month,
                axis=1,
            )

        # ------------------------------------------------------
        # Graceful fallback if older DLPD files do not contain
        # all source columns.
        # ------------------------------------------------------

        if "MONTH" in dataframe.columns:
            return dataframe["MONTH"].apply(
                cls._normalize_month_value,
            )

        if "THBLREK" in dataframe.columns:
            return dataframe["THBLREK"].apply(
                cls._normalize_month_value,
            )

        if "THBL" in dataframe.columns:
            return dataframe["THBL"].apply(
                cls._normalize_month_value,
            )

        return pd.Series(
            [None] * len(dataframe),
            index=dataframe.index,
            dtype="object",
        )

    # ==========================================================
    # TRANSFORM
    # ==========================================================

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = self.normalize_columns(
            dataframe,
        )

        dataframe = self.clean_idpel(
            dataframe,
        )

        dataframe = self.remove_duplicates(
            dataframe,
        )

        dataframe = self.clean_strings(
            dataframe,
            self.STRING_COLUMNS,
        )

        dataframe = self.clean_numeric(
            dataframe,
            self.NUMERIC_COLUMNS,
        )

        dataframe = self.clean_dates(
            dataframe,
            self.DATE_COLUMNS,
        )

        # ======================================================
        # ENSURE SOURCE PERIOD COLUMNS EXIST
        # ======================================================

        if "THBL" not in dataframe.columns:
            dataframe["THBL"] = ""

        if "THBLREK" not in dataframe.columns:
            dataframe["THBLREK"] = ""

        dataframe["THBL"] = (
            dataframe["THBL"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        dataframe["THBLREK"] = (
            dataframe["THBLREK"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # ======================================================
        # MONTH
        #
        # IMPORTANT:
        #
        # Do NOT take MONTH from the first Excel row.
        #
        # Resolve it independently for every record using:
        #
        #     THBL
        #       ↓
        #   DLPD_TGLBACA
        #       ↓
        #     THBLREK
        #
        # ======================================================

        dataframe["MONTH"] = (
            self._resolve_month_per_row(
                dataframe,
            )
        )

        dataframe["MONTH"] = (
            dataframe["MONTH"]
            .apply(
                self._normalize_month_value,
            )
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # ======================================================
        # DATASET
        # ======================================================

        if "DATASET" not in dataframe.columns:
            dataframe["DATASET"] = "DLPD"

        dataframe["DATASET"] = (
            dataframe["DATASET"]
            .fillna("DLPD")
            .astype(str)
            .str.strip()
        )

        # ======================================================
        # FINAL COLUMN ORDER / RESULT
        # ======================================================

        return dataframe