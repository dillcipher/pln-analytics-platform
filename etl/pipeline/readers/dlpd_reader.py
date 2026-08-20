"""
DLPD Reader
===========
Reads DLPD Pascabayar (postpaid) and DLPD Prabayar (prepaid) files.
Both feed the same DLPD Monitoring module, so this reader also tags each
row with a `SEGMENT` column so the transformer can union them into one
`dlpd_customer` dataset without losing which billing segment a customer
belongs to.

Pascabayar has no UNITUPI column (only UNITAP/UNITUP) — that gap is
intentionally left for the transformer's unit-hierarchy resolver to fill
in via a lookup built from sources that DO carry the full hierarchy.
"""
from __future__ import annotations

import pandas as pd

from etl.config.schema_registry import SCHEMA_REGISTRY, SourceType
from etl.pipeline.discovery import DiscoveredFile
from etl.pipeline.readers.base_reader import coerce_dtypes, read_raw_sheet, validate_required_columns


def read_dlpd_pascabayar(file: DiscoveredFile) -> tuple[pd.DataFrame, list[str]]:
    schema = SCHEMA_REGISTRY[SourceType.DLPD_PASCABAYAR]
    df = read_raw_sheet(file)
    problems = validate_required_columns(df, schema, file.path)
    df = coerce_dtypes(df, schema)

    df["SEGMENT"] = "PASCABAYAR"
    # THBLREK (e.g. 202607) is both the billing period AND the month key.
    df["THBLREK"] = df["THBLREK"].astype(str).str.strip()
    df["MONTH_KEY"] = df["THBLREK"].str[:6]
    df["UNITUPI"] = None  # resolved later by unit_hierarchy transformer

    return df, problems


def read_dlpd_prabayar(file: DiscoveredFile) -> tuple[pd.DataFrame, list[str]]:
    schema = SCHEMA_REGISTRY[SourceType.DLPD_PRABAYAR]
    df = read_raw_sheet(file)
    problems = validate_required_columns(df, schema, file.path)
    df = coerce_dtypes(df, schema)

    df["SEGMENT"] = "PRABAYAR"
    df["THBL"] = df["THBL"].astype(str).str.strip()
    df["MONTH_KEY"] = df["THBL"].str[:6]

    return df, problems
