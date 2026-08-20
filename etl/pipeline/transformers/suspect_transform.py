"""
Suspect Analytics Transformer
==============================
Produces the three datasets the Suspect Analytics module's three pages
are read directly from:

    suspect_detail  -> Detail Page  (one row per instant reading)
    suspect_main    -> Main Page    (Suspect x Pelanggan x Frekuensi)
    suspect_summary -> Summary Page (location x anomaly-category pivot)

`suspect_main` and `suspect_summary` are precomputed here (rather than
aggregated on every dashboard request) because they are cheap to
recompute at ETL time and expensive to recompute per-request across
millions of detail rows — this is the "Generate Summary Tables" /
"Generate Dashboard Tables" step from the ETL flow.
"""
from __future__ import annotations

import logging

import pandas as pd

from etl.config.schema_registry import SUSPECT_CATEGORIES

logger = logging.getLogger(__name__)


def build_suspect_detail(period_frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate every period-slice file (already read individually)
    into one detail table, deduping any reading that appears in more
    than one slice (can happen at slice boundaries)."""
    if not period_frames:
        return pd.DataFrame()

    combined = pd.concat(period_frames, ignore_index=True)
    key_cols = [c for c in ("LOCATION_CODE", "READ_DATE", "SUSPECT_NAME") if c in combined.columns]
    before = len(combined)
    if key_cols:
        combined = combined.drop_duplicates(subset=key_cols, keep="last")
    removed = before - len(combined)
    if removed:
        logger.info("Removed %d duplicate suspect reading(s)", removed)

    if "SUSPECT_NAME" in combined.columns:
        combined["SUSPECT_NAME"] = combined["SUSPECT_NAME"].astype(str).str.strip().str.upper()

    return combined


def build_suspect_main(detail: pd.DataFrame) -> pd.DataFrame:
    """One row per (MONTH_KEY, SUSPECT_NAME): distinct customers flagged
    and total occurrence frequency."""
    if detail.empty:
        return pd.DataFrame(columns=["MONTH_KEY", "SUSPECT_NAME", "PELANGGAN", "FREKUENSI"])

    grouped = (
        detail.groupby(["MONTH_KEY", "SUSPECT_NAME"])
        .agg(
            PELANGGAN=("LOCATION_CODE", "nunique"),
            FREKUENSI=("LOCATION_CODE", "size"),
        )
        .reset_index()
        .sort_values(["MONTH_KEY", "FREKUENSI"], ascending=[True, False])
    )
    return grouped


def build_suspect_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """Pivot: one row per location per month, one column per anomaly
    category (the fixed SUSPECT_CATEGORIES set), values = occurrence
    count, plus a Grand Total column — matching the Summary Page spec
    exactly."""
    if detail.empty:
        return pd.DataFrame()

    dims = [
        c for c in (
            "MONTH_KEY", "LOCATION_CODE", "LOCATION_NAME", "UNITUPI",
            "UNITAP", "UNITUP", "TARIFF", "POWER",
        )
        if c in detail.columns
    ]

    pivot = pd.pivot_table(
        detail,
        index=dims,
        columns="SUSPECT_NAME",
        values="READ_DATE",
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    pivot.columns.name = None

    # Guarantee every known category column exists even if a given month
    # happened to have zero occurrences of it (keeps the frontend table
    # schema stable month-to-month).
    for category in SUSPECT_CATEGORIES:
        if category not in pivot.columns:
            pivot[category] = 0

    category_cols = [c for c in SUSPECT_CATEGORIES if c in pivot.columns]
    pivot["GRAND_TOTAL"] = pivot[category_cols].sum(axis=1)

    ordered = dims + category_cols + ["GRAND_TOTAL"]
    return pivot[ordered].sort_values("GRAND_TOTAL", ascending=False)
