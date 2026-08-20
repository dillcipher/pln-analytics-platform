"""
Export utilities shared by every module's "Export Excel" / "Export CSV"
button. Deliberately generated server-side from the already-filtered
DuckDB result (not client-side from whatever rows happen to be loaded in
the browser) so an export always reflects the full filtered result set,
not just the current page — this matters once tables have hundreds of
thousands of rows and the grid only renders a page at a time.

Split into pure "rows -> bytes" builders (unit-testable with zero
FastAPI/web dependency) and a thin FastAPI response wrapper.
"""
from __future__ import annotations

import csv
import io
from typing import Any


def rows_to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")  # BOM so Excel opens UTF-8 correctly


def rows_to_xlsx_bytes(rows: list[dict[str, Any]], sheet_name: str = "Data") -> bytes:
    import xlsxwriter  # imported lazily so environments that only need CSV export stay lighter

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    sheet = workbook.add_worksheet(sheet_name[:31] or "Data")

    header_format = workbook.add_format({"bold": True, "bg_color": "#1F2937", "font_color": "#FFFFFF"})

    if rows:
        headers = list(rows[0].keys())
        for col_idx, header in enumerate(headers):
            sheet.write(0, col_idx, header, header_format)
        for row_idx, row in enumerate(rows, start=1):
            for col_idx, header in enumerate(headers):
                value = row.get(header)
                sheet.write(row_idx, col_idx, "" if value is None else value)
        sheet.autofilter(0, 0, len(rows), len(headers) - 1)
        sheet.freeze_panes(1, 0)

    workbook.close()
    return buffer.getvalue()


def build_export_filename(module: str, month_key: str, extension: str) -> str:
    return f"pln_{module}_{month_key}.{extension}"
