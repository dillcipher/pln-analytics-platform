"""Runtime fix for Excel/Pandas IDPEL formatting differences.

Excel can expose the same customer ID as a plain integer, a ``.0`` float,
or scientific notation. Coordinate joins must normalize those formatting
artifacts consistently on both DLPD and CUSTOMER_LOCATION sides.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.etl.merger.monthly_merger import MonthlyMerger


_INSTALLED = False


def _normalize_idpel_series(series: pd.Series) -> pd.Series:
    def normalize(value) -> str:
        if pd.isna(value):
            return ""

        text = str(value).strip()
        if not text:
            return ""

        # Excel/Pandas integer-like floats: 123456.0 -> 123456.
        if re.fullmatch(r"[+-]?\d+\.0+", text):
            return text.split(".", 1)[0]

        # Scientific notation: 1.71002615379E+11 -> 171002615379.
        # Only normalize when the value is exactly integral so we never
        # round a genuinely non-integral identifier.
        if "e" in text.lower():
            try:
                number = Decimal(text)
                if number == number.to_integral_value():
                    return format(number.quantize(Decimal("1")), "f")
            except (InvalidOperation, ValueError):
                pass

        return text

    return series.apply(normalize).astype(str).str.strip()


def install_idpel_normalization_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    MonthlyMerger._normalize_idpel_series = staticmethod(
        _normalize_idpel_series
    )
    _INSTALLED = True
