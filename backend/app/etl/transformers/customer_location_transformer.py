from __future__ import annotations

import math
import re

import pandas as pd

from app.etl.transformers.base_transformer import BaseTransformer


class CustomerLocationTransformer(BaseTransformer):
    """
    Transform customer location / coordinate master data.

    Supported source formats:

    - DIL_SALDO_MASK
    - TO_PRABAYAR
    - TO_PASCABAYAR

    Coordinate convention:

        KOORDINAT_X = LATITUDE
        KOORDINAT_Y = LONGITUDE

    Target area:

        Lampung / Indonesia

    Valid latitude:

        -11 <= latitude <= 7

    Valid longitude:

        95 <= longitude <= 141

    Supported coordinate formats:

    1. Normal decimal

        -5.4203011111
        105.2164311111

    2. Reversed X/Y

        X = 105.3523432
        Y = -5.3452819

    3. Packed coordinates with dots

        -5.424.332.222
        1.051.931.322.222

    4. Packed coordinates without dots

        -54107922222
        1049934522222

    5. DIL apostrophe-corrupted decimal format

        105.26'105.11111
        105.25'105.11111
        105.2'105.022222

    Apostrophe format is normalized by removing the apostrophe:

        105.26'105.11111
        -> 105.2610511111

    Reversed coordinates are automatically swapped.
    """

    # ==========================================================
    # OUTPUT COLUMNS
    # ==========================================================

    LOCATION_COLUMNS = [
        "IDPEL",
        "UNITUPI",
        "UNITAP",
        "UNITUP",
        "KOORDINAT_X",
        "KOORDINAT_Y",
    ]

    COORDINATE_COLUMNS = [
        "KOORDINAT_X",
        "KOORDINAT_Y",
    ]

    # ==========================================================
    # VALID RANGE
    # ==========================================================

    LATITUDE_MIN = -11.0
    LATITUDE_MAX = 7.0

    LONGITUDE_MIN = 95.0
    LONGITUDE_MAX = 141.0

    # ==========================================================
    # INVALID TEXT
    # ==========================================================

    INVALID_TEXT_VALUES = {
        "",
        "NAN",
        "NONE",
        "NULL",
        "NA",
        "N/A",
        "NIL",
        "-",
        "--",
        "TIDAKADA",
        "TIDAKTERSEDIA",
    }

    # ==========================================================
    # BASIC FLOAT
    # ==========================================================

    @staticmethod
    def _finite(
        value: object,
    ) -> float | None:

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            number = float(value)

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

        if not math.isfinite(number):
            return None

        return number

    # ==========================================================
    # REJECT ZERO / SUB-DEGREE VALUES
    # ==========================================================

    @staticmethod
    def _reject_small(
        value: float | None,
    ) -> float | None:

        if value is None:
            return None

        if not math.isfinite(value):
            return None

        if abs(value) < 1.0:
            return None

        return float(value)

    # ==========================================================
    # APOSTROPHE CORRUPTION
    # ==========================================================

    @classmethod
    def _parse_apostrophe_coordinate(
        cls,
        text: str,
    ) -> float | None:
        """
        Parse the DIL apostrophe-corrupted coordinate format.

        The actual corruption found in the DIL files is for example:

            105.26'105.11111
            105.25'105.11111
            105.2'105.022222
            105.3'105.0194

        The apostrophe is a corrupted separator between two numeric
        fragments.

        The correct normalization is NOT simply:
            text.replace("'", "")

        because that produces:
            105.26105.11111

        Instead:
            - preserve the decimal point from the left fragment
            - remove decimal points from the right fragment
            - append the right-hand digits to the left fraction

        Examples:

            105.26'105.11111
                -> 105.2610511111

            105.25'105.11111
                -> 105.2510511111

            105.2'105.022222
                -> 105.2105022222

            105.3'105.0194
                -> 105.31050194
        """

        if not text:
            return None

        text = str(text).strip()

        if "'" not in text:
            return None

        # This corruption pattern is expected to contain exactly
        # one apostrophe.
        if text.count("'") != 1:
            return None

        # Reject clearly invalid quoted content.
        if '"' in text:
            return None

        left, right = text.split("'", 1)

        left = left.strip()
        right = right.strip()

        if not left or not right:
            return None

        # Left side must be a normal signed decimal number.
        if not re.fullmatch(
            r"[+-]?\d+(?:\.\d+)?",
            left,
        ):
            return None

        # Right side can contain one or more decimal dots because
        # the DIL source itself is corrupted.
        if not re.fullmatch(
            r"\d+(?:\.\d+)*",
            right,
        ):
            return None

        # The dots in the right fragment are separators/corruption.
        right_digits = right.replace(".", "")

        if not right_digits:
            return None

        # Preserve the first decimal point from the left side.
        if "." in left:

            integer_part, fractional_part = left.split(
                ".",
                1,
            )

            if not fractional_part:
                return None

            cleaned = (
                f"{integer_part}."
                f"{fractional_part}"
                f"{right_digits}"
            )

        else:
            # Defensive fallback if the left side is an integer.
            cleaned = f"{left}.{right_digits}"

        if not re.fullmatch(
            r"[+-]?\d+(?:\.\d+)?",
            cleaned,
        ):
            return None

        number = cls._finite(
            cleaned,
        )

        return cls._reject_small(
            number,
        )

    # ==========================================================
    # PACKED FORMAT WITH DOTS
    # ==========================================================

    @classmethod
    def _parse_packed(
        cls,
        text: str,
    ) -> float | None:
        """
        Parse known DIL packed numeric format.

        Examples:

            -5.424.332.222
                -> -5.424332222

            1.051.931.322.222
                -> 105.1931322222

        Apostrophe-containing values are handled separately
        by _parse_apostrophe_coordinate().
        """

        if not text:
            return None

        text = str(text).strip()

        if "'" in text or '"' in text:
            return None

        negative = text.startswith("-")

        unsigned = text.lstrip("+-")

        if not unsigned:
            return None

        # Packed format requires at least two dots.
        if unsigned.count(".") < 2:
            return None

        parts = unsigned.split(".")

        if len(parts) < 3:
            return None

        if any(
            not part.isdigit()
            for part in parts
        ):
            return None

        digits = "".join(parts)

        if not digits:
            return None

        digit_count = len(digits)

        # ======================================================
        # Known DIL packed patterns
        #
        # Latitude:
        #
        #   5.424.332.222
        #   -> 5.424332222
        #
        # Longitude:
        #
        #   1.051.931.322.222
        #   -> 105.1931322222
        #
        # <= 10 digits:
        #   one integer digit
        #
        # > 10 digits:
        #   three integer digits
        # ======================================================

        if digit_count <= 10:
            integer_digits = 1
        else:
            integer_digits = 3

        if digit_count <= integer_digits:
            return None

        integer_part = digits[:integer_digits]
        fraction_part = digits[integer_digits:]

        try:
            integer_value = int(
                integer_part,
            )

            fraction_value = int(
                fraction_part,
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

        divisor = 10 ** len(
            fraction_part,
        )

        number = (
            integer_value
            + (
                fraction_value
                / divisor
            )
        )

        if negative:
            number = -number

        if not math.isfinite(number):
            return None

        return cls._reject_small(
            number,
        )

    # ==========================================================
    # PACKED FORMAT WITHOUT DOTS
    # ==========================================================

    @classmethod
    def _parse_packed_no_dots(
        cls,
        text: str,
    ) -> float | None:
        """
        Parse packed DIL coordinate values that have lost
        their decimal separators.

        Examples:

            -54107922222
                -> -5.4107922222

            1049934522222
                -> 104.9934522222

        Interpretation:

            latitude:
                1 integer digit + fractional digits

            longitude:
                3 integer digits + fractional digits
        """

        if not text:
            return None

        text = str(text).strip()

        if "'" in text or '"' in text:
            return None

        if not re.fullmatch(
            r"[+-]?\d+",
            text,
        ):
            return None

        negative = text.startswith("-")

        digits = text.lstrip("+-")

        if not digits:
            return None

        digit_count = len(digits)

        # Typical latitude:
        #
        #   54107922222
        #
        # = 5 + 10 fractional digits

        if digit_count == 11:
            integer_digits = 1

        # Typical longitude:
        #
        #   1049934522222
        #
        # = 3 + 10 fractional digits

        elif digit_count >= 12:
            integer_digits = 3

        else:
            return None

        if digit_count <= integer_digits:
            return None

        integer_part = digits[:integer_digits]

        fraction_part = digits[
            integer_digits:
        ]

        try:
            integer_value = int(
                integer_part,
            )

            fraction_value = int(
                fraction_part,
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

        divisor = 10 ** len(
            fraction_part,
        )

        number = (
            integer_value
            + (
                fraction_value
                / divisor
            )
        )

        if negative:
            number = -number

        if not math.isfinite(number):
            return None

        return cls._reject_small(
            number,
        )

    # ==========================================================
    # NORMALIZE ONE VALUE
    # ==========================================================

    @classmethod
    def _normalize_coordinate(
        cls,
        value: object,
    ) -> float | None:
        """
        Normalize a single coordinate.

        Supported:

        - normal decimal
        - decimal comma
        - DIL apostrophe corruption
        - packed with dots
        - packed without dots
        - numeric Excel values
        """

        if value is None:
            return None

        # ======================================================
        # Numeric Excel values
        # ======================================================

        if isinstance(
            value,
            (int, float),
        ) and not isinstance(
            value,
            bool,
        ):

            number = cls._finite(
                value,
            )

            if number is not None:

                # Normal coordinate.
                if (
                    cls.LATITUDE_MIN
                    <= number
                    <= cls.LONGITUDE_MAX
                    and abs(number) >= 1.0
                ):
                    return cls._reject_small(
                        number,
                    )

                # Excel may have converted a packed value
                # into a numeric value.
                packed = cls._parse_packed_no_dots(
                    str(value),
                )

                if packed is not None:
                    return packed

            return None

        # ======================================================
        # String
        # ======================================================

        text = str(value).strip()

        if not text:
            return None

        text = re.sub(
            r"\s+",
            "",
            text,
        )

        # Remove wrapping double quotes only.
        text = text.strip(
            '"',
        )

        if text.upper() in cls.INVALID_TEXT_VALUES:
            return None

        # ======================================================
        # DIL APOSTROPHE FORMAT
        # ======================================================
        #
        # This MUST happen before standard decimal parsing.
        #
        # Example:
        #
        #   105.26'105.11111
        #
        # becomes:
        #
        #   105.2610511111
        #
        # This is the corruption pattern actually present in
        # the DIL files.
        # ======================================================

        if "'" in text:

            apostrophe_value = (
                cls._parse_apostrophe_coordinate(
                    text,
                )
            )

            if apostrophe_value is not None:
                return apostrophe_value

            return None

        # ======================================================
        # Decimal comma
        # ======================================================

        if (
            "," in text
            and "." not in text
        ):
            text = text.replace(
                ",",
                ".",
            )

        # ======================================================
        # Packed format WITH dots
        # ======================================================

        packed = cls._parse_packed(
            text,
        )

        if packed is not None:
            return packed

        # ======================================================
        # Packed format WITHOUT dots
        # ======================================================

        packed_no_dots = (
            cls._parse_packed_no_dots(
                text,
            )
        )

        if packed_no_dots is not None:
            return packed_no_dots

        # ======================================================
        # Standard decimal
        # ======================================================

        if re.fullmatch(
            r"[+-]?\d+(?:\.\d+)?",
            text,
        ):

            number = cls._finite(
                text,
            )

            return cls._reject_small(
                number,
            )

        # ======================================================
        # Clean harmless characters
        # ======================================================

        cleaned = re.sub(
            r"[^0-9+\-.,]",
            "",
            text,
        )

        if not cleaned:
            return None

        # ======================================================
        # Decimal comma
        # ======================================================

        if (
            "," in cleaned
            and "." not in cleaned
        ):
            cleaned = cleaned.replace(
                ",",
                ".",
            )

        # ======================================================
        # Final numeric parse
        # ======================================================

        number = cls._finite(
            cleaned,
        )

        return cls._reject_small(
            number,
        )

    # ==========================================================
    # LATITUDE
    # ==========================================================

    @classmethod
    def _is_latitude(
        cls,
        value: float | None,
    ) -> bool:

        if value is None:
            return False

        return (
            cls.LATITUDE_MIN
            <= value
            <= cls.LATITUDE_MAX
            and abs(value) >= 1.0
        )

    # ==========================================================
    # LONGITUDE
    # ==========================================================

    @classmethod
    def _is_longitude(
        cls,
        value: float | None,
    ) -> bool:

        if value is None:
            return False

        return (
            cls.LONGITUDE_MIN
            <= value
            <= cls.LONGITUDE_MAX
            and abs(value) >= 1.0
        )

    # ==========================================================
    # NORMALIZE COORDINATE PAIR
    # ==========================================================

    @classmethod
    def _normalize_coordinate_pair(
        cls,
        x_value: object,
        y_value: object,
    ) -> tuple[
        float | None,
        float | None,
    ]:
        """
        Normalize X/Y as a pair.

        Normal:

            X = latitude
            Y = longitude

        Reversed:

            X = longitude
            Y = latitude

        Reversed values are automatically swapped.

        Anything that cannot be confidently classified as
        a latitude/longitude pair is discarded.
        """

        x = cls._normalize_coordinate(
            x_value,
        )

        y = cls._normalize_coordinate(
            y_value,
        )

        # ======================================================
        # Normal orientation
        # ======================================================

        if (
            cls._is_latitude(x)
            and cls._is_longitude(y)
        ):

            return (
                float(x),
                float(y),
            )

        # ======================================================
        # Reversed orientation
        # ======================================================

        if (
            cls._is_longitude(x)
            and cls._is_latitude(y)
        ):

            return (
                float(y),
                float(x),
            )

        # ======================================================
        # Invalid
        # ======================================================

        return (
            None,
            None,
        )

    # ==========================================================
    # MAP SOURCE COORDINATES
    # ==========================================================

    @staticmethod
    def _map_source_coordinate_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Map source-specific coordinate columns into the
        canonical CUSTOMER_LOCATION schema.

        Existing DIL:

            KOORDINAT_X -> latitude
            KOORDINAT_Y -> longitude

        TO files:

            LATITUDE -> latitude
            LONGITUDE -> longitude

        Canonical:

            KOORDINAT_X = latitude
            KOORDINAT_Y = longitude
        """

        dataframe = dataframe.copy()

        latitude_candidates = (
            "LATITUDE",
            "LAT",
        )

        longitude_candidates = (
            "LONGITUDE",
            "LON",
            "LNG",
        )

        # ======================================================
        # LATITUDE
        # ======================================================

        if "LATITUDE" in dataframe.columns:

            dataframe["KOORDINAT_X"] = (
                dataframe["LATITUDE"]
            )

        elif "KOORDINAT_X" not in dataframe.columns:

            for column in latitude_candidates:

                if column in dataframe.columns:

                    dataframe["KOORDINAT_X"] = (
                        dataframe[column]
                    )

                    break

        # ======================================================
        # LONGITUDE
        # ======================================================

        if "LONGITUDE" in dataframe.columns:

            dataframe["KOORDINAT_Y"] = (
                dataframe["LONGITUDE"]
            )

        elif "KOORDINAT_Y" not in dataframe.columns:

            for column in longitude_candidates:

                if column in dataframe.columns:

                    dataframe["KOORDINAT_Y"] = (
                        dataframe[column]
                    )

                    break

        # ======================================================
        # GUARANTEE
        # ======================================================

        if "KOORDINAT_X" not in dataframe.columns:
            dataframe["KOORDINAT_X"] = None

        if "KOORDINAT_Y" not in dataframe.columns:
            dataframe["KOORDINAT_Y"] = None

        return dataframe

    # ==========================================================
    # CLEAN COORDINATES
    # ==========================================================

    @classmethod
    def _clean_coordinates(
        cls,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize coordinates row-by-row as a pair.

        This automatically:

        - fixes reversed X/Y
        - parses normal decimals
        - parses packed DIL coordinates
        - parses apostrophe-corrupted DIL coordinates
        """

        dataframe = dataframe.copy()

        if "KOORDINAT_X" not in dataframe.columns:
            dataframe["KOORDINAT_X"] = None

        if "KOORDINAT_Y" not in dataframe.columns:
            dataframe["KOORDINAT_Y"] = None

        pairs = [
            cls._normalize_coordinate_pair(
                x,
                y,
            )
            for x, y in zip(
                dataframe["KOORDINAT_X"],
                dataframe["KOORDINAT_Y"],
            )
        ]

        dataframe["KOORDINAT_X"] = [
            pair[0]
            for pair in pairs
        ]

        dataframe["KOORDINAT_Y"] = [
            pair[1]
            for pair in pairs
        ]

        dataframe["KOORDINAT_X"] = pd.to_numeric(
            dataframe["KOORDINAT_X"],
            errors="coerce",
        )

        dataframe["KOORDINAT_Y"] = pd.to_numeric(
            dataframe["KOORDINAT_Y"],
            errors="coerce",
        )

        return dataframe

    # ==========================================================
    # TRANSFORM
    # ==========================================================

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Transform DIL / customer-location /
        coordinate-master data.
        """

        dataframe = dataframe.copy()

        # ======================================================
        # NORMALIZE COLUMN NAMES
        # ======================================================

        dataframe = self.normalize_columns(
            dataframe,
        )

        # ======================================================
        # MAP SOURCE COORDINATE COLUMNS
        # ======================================================

        dataframe = (
            self._map_source_coordinate_columns(
                dataframe,
            )
        )

        # ======================================================
        # CLEAN IDPEL
        # ======================================================

        dataframe = self.clean_idpel(
            dataframe,
        )

        # ======================================================
        # GUARANTEE REQUIRED COLUMNS
        # ======================================================

        for column in self.LOCATION_COLUMNS:

            if column not in dataframe.columns:
                dataframe[column] = None

        # ======================================================
        # CLEAN ORGANIZATIONAL FIELDS
        # ======================================================

        dataframe = self.clean_strings(
            dataframe,
            [
                "UNITUPI",
                "UNITAP",
                "UNITUP",
            ],
        )

        # ======================================================
        # CLEAN COORDINATES
        # ======================================================

        dataframe = self._clean_coordinates(
            dataframe,
        )

        # ======================================================
        # REMOVE DUPLICATES
        # ======================================================

        dataframe = self.remove_duplicates(
            dataframe,
        )

        # ======================================================
        # FINAL COLUMNS
        # ======================================================

        dataframe = dataframe[
            self.LOCATION_COLUMNS
        ].copy()

        # ======================================================
        # DATASET
        # ======================================================

        dataframe["DATASET"] = (
            "CUSTOMER_LOCATION"
        )

        return dataframe