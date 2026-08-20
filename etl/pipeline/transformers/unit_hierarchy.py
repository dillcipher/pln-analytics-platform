"""
Unit Hierarchy Resolver
========================
PLN's organizational hierarchy is UNITUPI (UID, wilayah/regional) >
UNITAP (UP3, area) > UNITUP (ULP, unit layanan pelanggan). Not every
source carries the full hierarchy — DLPD Pascabayar, for instance, only
has UNITAP/UNITUP.

Rather than leaving UNITUPI null (which would break global filters that
expect a working UNITUPI dropdown for every record), we build a
UNITAP -> UNITUPI lookup from whichever sources DO carry the full chain
(DLPD Prabayar and Suspect ANEV both do) and use it to backfill any
source that's missing UNITUPI. UNITAP is the reliable join key since
every source in this platform carries it.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def build_hierarchy_lookup(*sources: pd.DataFrame) -> pd.DataFrame:
    """Build a deduplicated UNITAP -> UNITUPI (+ UNITUP for reference)
    lookup table from any number of source DataFrames that carry the
    full hierarchy. Sources missing UNITUPI/UNITAP entirely are skipped."""
    frames = []
    for df in sources:
        if {"UNITUPI", "UNITAP"}.issubset(df.columns):
            subset = df[["UNITUPI", "UNITAP"]].dropna(subset=["UNITAP"])
            frames.append(subset)

    if not frames:
        logger.warning("No source carried a full UNITUPI/UNITAP hierarchy — lookup will be empty")
        return pd.DataFrame(columns=["UNITAP", "UNITUPI"])

    combined = pd.concat(frames, ignore_index=True)
    # If a UNITAP maps to more than one UNITUPI in the data (shouldn't
    # happen in a clean hierarchy, but real data is real data), keep the
    # most frequent pairing rather than silently picking the first row.
    lookup = (
        combined.dropna(subset=["UNITUPI"])
        .groupby("UNITAP")["UNITUPI"]
        .agg(lambda s: s.value_counts().idxmax())
        .reset_index()
    )
    return lookup


def apply_hierarchy(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    """Fill missing UNITUPI values in `df` by joining on UNITAP against
    `lookup`. Rows whose UNITAP has no known mapping keep UNITUPI as-is
    (typically null) rather than raising — a monitoring dashboard should
    degrade gracefully, not crash, on an unmapped unit."""
    if "UNITAP" not in df.columns:
        return df

    df = df.copy()
    if "UNITUPI" not in df.columns:
        df["UNITUPI"] = None

    merged = df.merge(
        lookup.rename(columns={"UNITUPI": "_UNITUPI_LOOKUP"}),
        on="UNITAP",
        how="left",
    )
    merged["UNITUPI"] = merged["UNITUPI"].fillna(merged["_UNITUPI_LOOKUP"])
    merged = merged.drop(columns=["_UNITUPI_LOOKUP"])

    unresolved = merged["UNITUPI"].isna().sum()
    if unresolved:
        logger.warning("%d row(s) still missing UNITUPI after hierarchy resolution", unresolved)

    return merged
