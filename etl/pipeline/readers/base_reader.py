"""
Base reader shared by every source-specific reader.

Responsibilities kept here (common to all sources):
    - Read the correct sheet from the workbook
    - Standardize column names (strip whitespace, uppercase, spaces -> underscore)
    - Coerce declared numeric/date columns per the schema registry
    - Tag every row with its originating file (traceability / debugging)

Responsibilities deliberately left to source-specific readers:
    - Any column renaming that is specific to one source's quirks
      (e.g. Pengecekan's "UNIT ULP" -> "UNITUP")
    - Any column additions specific to one source (e.g. SEGMENT for DLPD)
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from etl.config.schema_registry import SourceSchema
from etl.pipeline.discovery import DiscoveredFile

logger = logging.getLogger(__name__)


def _standardize_column_name(name: object) -> str:
    return str(name).strip().upper().replace(" ", "_")


def read_raw_sheet(file: DiscoveredFile) -> pd.DataFrame:
    """Read the full sheet for one discovered file with standardized headers."""
    df = pd.read_excel(file.path, sheet_name=file.sheet_name, engine="openpyxl")
    df.columns = [_standardize_column_name(c) for c in df.columns]
    df["_SOURCE_FILE"] = file.path.name
    return df


def coerce_dtypes(df: pd.DataFrame, schema: SourceSchema) -> pd.DataFrame:
    """Apply the schema's declared numeric/date coercions in place-safe copy."""
    df = df.copy()

    for col in schema.numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in schema.date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def validate_required_columns(df: pd.DataFrame, schema: SourceSchema, source_path: Path) -> list[str]:
    """Return a list of human-readable validation problems (empty = valid).
    Does not raise — callers decide whether missing columns are fatal."""
    problems: list[str] = []
    present = set(df.columns)
    required = {c.strip().upper().replace(" ", "_") for c in schema.required_columns}
    missing = required - present
    if missing:
        problems.append(
            f"{source_path.name}: missing {len(missing)} required column(s): {sorted(missing)}"
        )
    return problems
