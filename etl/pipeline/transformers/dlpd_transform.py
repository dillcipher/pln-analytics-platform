"""
DLPD Transformer
================
Unions DLPD Pascabayar + Prabayar into one `dlpd_customer` dataset that
powers the DLPD Monitoring module, regardless of billing segment.

Steps: concat -> dedupe (last file wins on a duplicated primary key) ->
resolve UNITUPI via the hierarchy lookup -> clean obviously-missing
values in key display fields.
"""
from __future__ import annotations

import logging

import pandas as pd

from etl.pipeline.transformers.unit_hierarchy import apply_hierarchy, build_hierarchy_lookup

logger = logging.getLogger(__name__)


def _dedupe(df: pd.DataFrame, primary_key: list[str]) -> pd.DataFrame:
    key_cols = [c for c in primary_key if c in df.columns]
    if not key_cols:
        return df
    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="last")
    removed = before - len(df)
    if removed:
        logger.info("Removed %d duplicate DLPD record(s) on key %s", removed, key_cols)
    return df


def transform_dlpd_customers(
    pascabayar_frames: list[pd.DataFrame],
    prabayar_frames: list[pd.DataFrame],
) -> pd.DataFrame:
    """Returns one unified, cleaned `dlpd_customer` DataFrame spanning
    every month present in the input frames."""
    pasca = pd.concat(pascabayar_frames, ignore_index=True) if pascabayar_frames else pd.DataFrame()
    pra = pd.concat(prabayar_frames, ignore_index=True) if prabayar_frames else pd.DataFrame()

    if not pasca.empty:
        pasca = _dedupe(pasca, ["IDPEL", "THBLREK"])
    if not pra.empty:
        pra = _dedupe(pra, ["IDPEL", "THBL"])

    # Prabayar carries the full UNITUPI/UNITAP/UNITUP chain — use it (plus
    # any other full-hierarchy source passed in later) to backfill Pascabayar.
    lookup = build_hierarchy_lookup(pra) if not pra.empty else build_hierarchy_lookup()
    if not pasca.empty and not lookup.empty:
        pasca = apply_hierarchy(pasca, lookup)

    combined = pd.concat([pasca, pra], ignore_index=True, sort=False)

    # Normalize a couple of universally-useful display/filter fields.
    if "NAMA" in combined.columns:
        combined["NAMA"] = combined["NAMA"].astype(str).str.strip()
    if "TARIF" in combined.columns:
        combined["TARIF"] = combined["TARIF"].astype(str).str.strip().str.upper()

    logger.info(
        "DLPD customer dataset: %d rows (%d Pascabayar, %d Prabayar)",
        len(combined), len(pasca), len(pra),
    )
    return combined
