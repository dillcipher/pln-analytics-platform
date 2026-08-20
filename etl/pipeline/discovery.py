"""
File Discovery
==============
Scans an input folder, opens each workbook once to read its sheet list
and one header row (cheap — no full data read), and classifies the file
against the `SCHEMA_REGISTRY` by column-signature overlap rather than by
filename substring matching. Filename matching is fragile in practice
(files get renamed, re-exported, re-shared with prefixes stripped) —
column signatures are not.

For the Suspect Analytics (ANEV/ANNEV) source, the month is *also*
encoded in the filename as a date range
(`17_ANEV_20260221-20260228.xlsx`), so we extract it there without
opening the file body. For all other sources the month is only known
after reading the data (from THBLREK / THBL / BULAN columns), so
`month_key_from_filename` is left as None at discovery time and resolved
later by the matching reader/transformer.

Never hardcode a month or year here — everything is derived from what's
on disk, so future months require zero code changes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from etl.config.schema_registry import SCHEMA_REGISTRY, SourceType

logger = logging.getLogger(__name__)

# Matches e.g. "17_ANEV_20260221-20260228.xlsx" or "17_ANNEV_20260311-20260320.xlsx"
# (the "ANNEV" spelling is a known upstream typo variant — both mean the same
# Suspect Analytics export and must be treated identically).
ANEV_FILENAME_PATTERN = re.compile(
    r"AN{1,2}EV_(?P<start>\d{8})-(?P<end>\d{8})", re.IGNORECASE
)

MIN_COLUMN_OVERLAP_RATIO = 0.7  # 70% of a schema's required columns must be present to match


@dataclass
class DiscoveredFile:
    """One Excel file discovered on disk, classified and (if derivable from
    the filename) tagged with its month. `sheet_name` is the ACTUAL sheet
    name found in the workbook (not necessarily the registry's canonical
    name) so downstream readers open the right sheet even if a source
    system renames tabs."""
    path: Path
    source_type: SourceType
    sheet_name: str
    month_key_from_filename: str | None  # "YYYYMM" or None if only derivable from data
    period_start: str | None = None      # "YYYYMMDD" — used for intra-month ordering
    period_end: str | None = None


def _pick_candidate_sheet(path: Path) -> str | None:
    """Open the workbook once, and pick the sheet most likely to hold
    data: prefer a sheet whose name matches one of the registry's known
    sheet names (case-insensitive), otherwise fall back to the first
    sheet in the workbook."""
    try:
        book = pd.ExcelFile(path, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - skip unreadable files, don't crash the run
        logger.warning("Could not open %s: %s", path.name, exc)
        return None

    known_names = {s.sheet_name.upper() for s in SCHEMA_REGISTRY.values()}
    for sheet in book.sheet_names:
        if sheet.strip().upper() in known_names:
            return sheet
    return book.sheet_names[0] if book.sheet_names else None


def _read_header_columns(path: Path, sheet_name: str) -> list[str] | None:
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, nrows=0, engine="openpyxl")
        return [str(c).strip() for c in df.columns]
    except Exception as exc:  # noqa: BLE001 - we want to skip, not crash, on one bad file
        logger.warning("Could not read header of %s (sheet=%s): %s", path.name, sheet_name, exc)
        return None


def _classify_by_columns(columns: list[str]) -> SourceType | None:
    """Score column overlap against every registered schema, return the
    best match above the minimum overlap threshold."""
    normalized = {c.strip().upper() for c in columns}
    best_type: SourceType | None = None
    best_score = 0.0

    for source_type, schema in SCHEMA_REGISTRY.items():
        required = {c.strip().upper() for c in schema.required_columns}
        if not required:
            continue
        overlap = len(normalized & required) / len(required)
        if overlap > best_score:
            best_score = overlap
            best_type = source_type

    if best_score >= MIN_COLUMN_OVERLAP_RATIO:
        return best_type

    logger.warning("No schema matched with sufficient confidence (best score=%.2f)", best_score)
    return None


def _extract_month_from_filename(filename: str) -> tuple[str | None, str | None, str | None]:
    """Returns (month_key 'YYYYMM', period_start 'YYYYMMDD', period_end 'YYYYMMDD')."""
    match = ANEV_FILENAME_PATTERN.search(filename)
    if not match:
        return None, None, None
    start, end = match.group("start"), match.group("end")
    return start[:6], start, end


def discover_files(input_dir: Path) -> list[DiscoveredFile]:
    """Recursively find every .xlsx/.xls file under `input_dir`, classify
    it, and (where possible) tag it with its month."""
    input_dir = Path(input_dir)
    candidates = sorted(
        [*input_dir.rglob("*.xlsx"), *input_dir.rglob("*.xls")]
    )
    # Ignore Excel lock files (~$file.xlsx) left behind by an open workbook
    candidates = [p for p in candidates if not p.name.startswith("~$")]

    discovered: list[DiscoveredFile] = []
    for path in candidates:
        sheet_name = _pick_candidate_sheet(path)
        if sheet_name is None:
            logger.warning("Skipping unreadable/empty workbook: %s", path.name)
            continue

        columns = _read_header_columns(path, sheet_name)
        if columns is None:
            logger.warning("Skipping unclassifiable file: %s", path.name)
            continue

        matched_type = _classify_by_columns(columns)
        if matched_type is None:
            logger.warning("Skipping unclassifiable file: %s", path.name)
            continue

        month_key, period_start, period_end = _extract_month_from_filename(path.name)
        discovered.append(
            DiscoveredFile(
                path=path,
                source_type=matched_type,
                sheet_name=sheet_name,
                month_key_from_filename=month_key,
                period_start=period_start,
                period_end=period_end,
            )
        )

    logger.info("Discovered %d classifiable file(s) under %s", len(discovered), input_dir)
    return discovered


def group_by_source_type(files: list[DiscoveredFile]) -> dict[SourceType, list[DiscoveredFile]]:
    grouped: dict[SourceType, list[DiscoveredFile]] = {st: [] for st in SourceType}
    for f in files:
        grouped[f.source_type].append(f)
    return grouped


def group_filename_dated_files_by_month(
    files: list[DiscoveredFile],
) -> dict[str, list[DiscoveredFile]]:
    """Group files that carry a month in their filename (ANEV/ANNEV) into
    {month_key: [files...]}, sorted by period_start so multi-part months
    concatenate in chronological order."""
    by_month: dict[str, list[DiscoveredFile]] = {}
    for f in files:
        if f.month_key_from_filename is None:
            continue
        by_month.setdefault(f.month_key_from_filename, []).append(f)

    for month_key in by_month:
        by_month[month_key].sort(key=lambda f: f.period_start or "")

    return by_month
