"""
Pengecekan Reader
=================
Reads P2TL field-inspection result files. This source uses PLN's
UID/UP3/ULP naming for the org hierarchy (with literal spaces in the
header: "UNIT ULP", "UNIT UP3", "UNIT UID") instead of the
UNITUPI/UNITAP/UNITUP naming used elsewhere — normalized here so every
downstream dataset speaks the same hierarchy vocabulary.

    UNIT UID -> UNITUPI   (Unit Induk Wilayah/Distribusi)
    UNIT UP3 -> UNITAP    (Unit Pelaksana Pelayanan Pelanggan)
    UNIT ULP -> UNITUP    (Unit Layanan Pelanggan)
"""
from __future__ import annotations

import pandas as pd

from etl.config.schema_registry import SCHEMA_REGISTRY, SourceType
from etl.pipeline.discovery import DiscoveredFile
from etl.pipeline.readers.base_reader import coerce_dtypes, read_raw_sheet, validate_required_columns

_HIERARCHY_RENAME = {
    "UNIT_UID": "UNITUPI",
    "UNIT_UP3": "UNITAP",
    "UNIT_ULP": "UNITUP",
}


def read_pengecekan(file: DiscoveredFile) -> tuple[pd.DataFrame, list[str]]:
    schema = SCHEMA_REGISTRY[SourceType.PENGECEKAN]
    df = read_raw_sheet(file)
    problems = validate_required_columns(df, schema, file.path)
    df = coerce_dtypes(df, schema)

    df = df.rename(columns=_HIERARCHY_RENAME)

    month_source = df["WAKTU_PERIKSA"] if "WAKTU_PERIKSA" in df.columns else df.get("BULAN")
    if month_source is not None:
        df["MONTH_KEY"] = pd.to_datetime(month_source, errors="coerce").dt.strftime("%Y%m")

    return df, problems
