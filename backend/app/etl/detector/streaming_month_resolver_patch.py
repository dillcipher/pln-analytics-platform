"""Memory-safe DLPD month resolution for very large XLSX workbooks.

The normal MonthResolver implementation uses pandas.read_excel() for the
entire DLPD sheet.  That is unsafe for 700+ MB workbooks on a small cloud
container because pandas materializes a large in-memory dataframe.

This module installs a narrow runtime patch that keeps the existing business
month rules unchanged while reading XLSX rows with openpyxl's read_only mode.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from app.etl.detector.month_resolver import MonthResolver
from app.etl.validator.validator import DatasetValidator


_INSTALLED = False


def _stream_read_dlpd_months(
    cls,
    filepath: Path,
    dataset: str,
    sheet_name: str,
) -> list[str]:
    """Resolve all DLPD business months without materializing the workbook."""
    filepath = Path(filepath)

    thbl_column = DatasetValidator.normalize_column("THBL")
    thblrek_column = DatasetValidator.normalize_column("THBLREK")
    date_column = DatasetValidator.normalize_column("DLPD_TGLBACA")
    required = {thbl_column, thblrek_column, date_column}

    workbook = None
    try:
        workbook = load_workbook(
            filename=filepath,
            read_only=True,
            data_only=True,
        )

        # Respect the already-resolved sheet name, but fall back safely if a
        # provider/version changed the workbook sheet metadata.
        if sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
        else:
            normalized_sheets = {
                str(name).strip().upper(): name
                for name in workbook.sheetnames
            }
            worksheet = workbook[
                normalized_sheets.get(
                    str(sheet_name).strip().upper(),
                    workbook.sheetnames[0],
                )
            ]

        header_row = None
        header_indexes: dict[str, int] = {}

        # Existing validator searches the first 15 rows. Keep the same
        # behavior, but do it with streaming openpyxl instead of pandas.
        for row_index, row in enumerate(
            worksheet.iter_rows(
                min_row=1,
                max_row=15,
                values_only=True,
            ),
            start=1,
        ):
            indexes = {}
            for column_index, value in enumerate(row):
                normalized = DatasetValidator.normalize_column(value)
                if normalized in required and normalized not in indexes:
                    indexes[normalized] = column_index

            if "IDPEL" in {
                DatasetValidator.normalize_column(value)
                for value in row
            } or "LOCATIONCODE" in {
                DatasetValidator.normalize_column(value)
                for value in row
            }:
                header_row = row_index
                header_indexes = indexes
                break

        # DLPD files normally expose IDPEL in the header. If a malformed file
        # does not, retain the old detector's header=0 behavior.
        if header_row is None:
            header_row = 1
            header_values = next(
                worksheet.iter_rows(
                    min_row=1,
                    max_row=1,
                    values_only=True,
                ),
                (),
            )
            header_indexes = {
                DatasetValidator.normalize_column(value): index
                for index, value in enumerate(header_values)
                if DatasetValidator.normalize_column(value) in required
            }

        months: set[str] = set()

        # If the required fields are absent, return [] exactly as the old
        # implementation did after its exception-safe fallback.
        if not header_indexes:
            return []

        max_index = max(header_indexes.values())

        for row in worksheet.iter_rows(
            min_row=header_row + 1,
            values_only=True,
        ):
            if not row:
                continue

            values = row[: max_index + 1]

            thbl = (
                values[header_indexes[thbl_column]]
                if thbl_column in header_indexes
                and header_indexes[thbl_column] < len(values)
                else None
            )
            thblrek = (
                values[header_indexes[thblrek_column]]
                if thblrek_column in header_indexes
                and header_indexes[thblrek_column] < len(values)
                else None
            )
            detail_date = (
                values[header_indexes[date_column]]
                if date_column in header_indexes
                and header_indexes[date_column] < len(values)
                else None
            )

            thbl_start = cls._month_start(thbl)
            thblrek_start = cls._month_start(thblrek)
            parsed_date = cls._parse_date(detail_date)

            if (
                parsed_date is not None
                and thbl_start is not None
                and thblrek_start is not None
            ):
                period_start = min(thbl_start, thblrek_start)
                period_month = max(thbl_start, thblrek_start)
                period_end = cls._month_end(period_month)

                if (
                    period_end is not None
                    and period_start <= parsed_date <= period_end
                ):
                    months.add(parsed_date.strftime("%Y%m"))
                    continue

            if (
                parsed_date is not None
                and (
                    thbl_start is not None
                    or thblrek_start is not None
                )
            ):
                months.add(parsed_date.strftime("%Y%m"))
                continue

            month = cls._normalize_month(thblrek)
            if month:
                months.add(month)
                continue

            month = cls._normalize_month(thbl)
            if month:
                months.add(month)

        return sorted(months)

    except Exception as exc:
        print(
            "[MonthResolver][streaming] "
            f"{filepath.name}: {exc}"
        )
        return []
    finally:
        if workbook is not None:
            try:
                workbook.close()
            except Exception:
                pass


def install_streaming_month_resolver_patch() -> None:
    """Install the memory-safe DLPD reader once per process."""
    global _INSTALLED
    if _INSTALLED:
        return

    MonthResolver._read_dlpd_months = classmethod(
        _stream_read_dlpd_months
    )
    _INSTALLED = True
