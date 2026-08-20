"""
Suspect Analytics (ANEV / ANNEV) Reader
========================================
Reads one period-slice file (e.g. `17_ANEV_20260221-20260228.xlsx`) of
Suspect Analytics instant-reading data. A single calendar month is made
of several of these files (10/10/8-11 day slices) — this reader handles
exactly ONE file; merging same-month slices together happens in
`etl/run_etl.py` after every file has been individually read.
"""
from __future__ import annotations

import pandas as pd

from etl.config.schema_registry import SCHEMA_REGISTRY, SourceType
from etl.pipeline.discovery import DiscoveredFile
from etl.pipeline.readers.base_reader import coerce_dtypes, read_raw_sheet, validate_required_columns


def read_suspect_anev(file: DiscoveredFile) -> tuple[pd.DataFrame, list[str]]:
    schema = SCHEMA_REGISTRY[SourceType.SUSPECT_ANEV]
    df = read_raw_sheet(file)
    problems = validate_required_columns(df, schema, file.path)
    df = coerce_dtypes(df, schema)

    df["MONTH_KEY"] = file.month_key_from_filename
    df["PERIOD_START"] = file.period_start
    df["PERIOD_END"] = file.period_end

    return df, problems
