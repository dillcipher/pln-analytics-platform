"""
Dataset Writer
==============
Writes a processed DataFrame out as a Hive-style partitioned dataset:

    data/processed/<dataset_name>/month=<YYYYMM>/part.parquet

Partitioning by month is what lets the backend's DuckDB layer prune
files it doesn't need (a query for July only ever opens the July
partition) and is what makes "the dashboard automatically detects the
new month" work — no manifest file to update, the backend just lists
whatever `month=` directories exist on disk.

Parquet (via pyarrow) is the target format end-to-end (matches the
architecture recommendation), but this writer degrades gracefully to
CSV if pyarrow isn't available in the environment it's run from, so the
pipeline is never fully blocked by a missing optional dependency. In
Colab and in the backend's `requirements.txt`, pyarrow is installed, so
this fallback should not normally trigger in production — it exists for
resilience and for environments (like a bare CI runner) where you may
only want to validate transformation logic without the full stack.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def write_partitioned_dataset(
    df: pd.DataFrame,
    output_root: Path,
    dataset_name: str,
    month_column: str = "MONTH_KEY",
) -> list[Path]:
    """Split `df` by `month_column` and write one partition file per
    month under `output_root/dataset_name/month=<key>/part.(parquet|csv)`.
    Returns the list of files written."""
    output_root = Path(output_root)
    dataset_dir = output_root / dataset_name
    written: list[Path] = []

    if df.empty:
        logger.warning("Dataset '%s' is empty — nothing written", dataset_name)
        return written

    if month_column not in df.columns:
        # No month dimension (e.g. a small static lookup table) — write as a single file.
        dataset_dir.mkdir(parents=True, exist_ok=True)
        written.append(_write_one(df, dataset_dir / "part"))
        return written

    for month_key, group in df.groupby(month_column):
        if month_key is None or (isinstance(month_key, float) and pd.isna(month_key)):
            logger.warning("Dropping %d row(s) of '%s' with no resolvable month", len(group), dataset_name)
            continue
        partition_dir = dataset_dir / f"month={month_key}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        written.append(_write_one(group, partition_dir / "part"))

    logger.info("Wrote %d partition(s) for dataset '%s'", len(written), dataset_name)
    return written


def _write_one(df: pd.DataFrame, path_no_ext: Path) -> Path:
    try:
        target = path_no_ext.with_suffix(".parquet")
        df.to_parquet(target, engine="pyarrow", index=False)
        return target
    except ImportError:
        logger.warning(
            "pyarrow not available — writing '%s' as CSV instead of Parquet. "
            "Install pyarrow for production use (already in requirements.txt).",
            path_no_ext.name,
        )
        target = path_no_ext.with_suffix(".csv")
        df.to_csv(target, index=False)
        return target
