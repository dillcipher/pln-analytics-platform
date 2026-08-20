"""
Converts a YYYYMM month key into an Indonesian display label.

Examples
--------
202507 -> Juli 2025
"202507" -> Juli 2025
"""

from __future__ import annotations

from app.domain.entities import MonthOption


_INDONESIAN_MONTHS = {
    "01": "Januari",
    "02": "Februari",
    "03": "Maret",
    "04": "April",
    "05": "Mei",
    "06": "Juni",
    "07": "Juli",
    "08": "Agustus",
    "09": "September",
    "10": "Oktober",
    "11": "November",
    "12": "Desember",
}


def month_key_to_label(
    month_key: str | int | None,
) -> str:

    if month_key is None:
        return ""

    month_key = str(month_key).strip()

    if len(month_key) != 6:
        return month_key

    year = month_key[:4]
    month = month_key[4:]

    return (
        f"{_INDONESIAN_MONTHS.get(month, month)} {year}"
    )


def month_keys_to_options(
    month_keys: list[str | int],
) -> list[MonthOption]:

    return [

        MonthOption(
            month_key=str(month_key),
            label=month_key_to_label(month_key),
        )

        for month_key in month_keys

    ]