"""
PLN Analytics Platform — ETL Entry Point
==========================================
Run this from Google Colab (see etl/notebooks/PLN_ETL_Colab.ipynb) or
locally. It implements the full flow from the architecture doc:

    Raw Excel -> discover -> read -> merge same-month files -> validate
    -> clean/transform -> generate summary/dashboard/lookup/detail
    tables -> write partitioned Parquet -> (you) push processed/ to GitHub

Usage:
    python -m etl.run_etl --input-dir data/raw --output-dir data/processed

Re-running is idempotent: it always reads *everything* currently in
`--input-dir` and regenerates the affected month partitions from
scratch, so adding new period files for a new month and re-running is
the entire "monthly update" procedure — no flags, no code changes.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from etl.config.schema_registry import SourceType
from etl.pipeline.discovery import discover_files, group_by_source_type
from etl.pipeline.readers.anev_reader import read_suspect_anev
from etl.pipeline.readers.dlpd_reader import read_dlpd_pascabayar, read_dlpd_prabayar
from etl.pipeline.readers.pengecekan_reader import read_pengecekan
from etl.pipeline.transformers.dlpd_transform import transform_dlpd_customers
from etl.pipeline.transformers.suspect_transform import (
    build_suspect_detail,
    build_suspect_main,
    build_suspect_summary,
)
from etl.pipeline.validators import ValidationReport, require_non_empty
from etl.pipeline.writers.parquet_writer import write_partitioned_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("etl.run_etl")


def run(input_dir: Path, output_dir: Path) -> ValidationReport:
    report = ValidationReport()

    logger.info("=" * 70)
    logger.info("STEP 1/6 — Discovering & classifying files in %s", input_dir)
    discovered = discover_files(input_dir)
    if not discovered:
        report.add_error(f"No classifiable Excel files found under {input_dir}")
        report.log_summary()
        return report
    by_source = group_by_source_type(discovered)
    for source_type, files in by_source.items():
        logger.info("  %-18s: %d file(s)", source_type.value, len(files))

    logger.info("=" * 70)
    logger.info("STEP 2/6 — Reading & merging files belonging to the same month")

    pascabayar_frames, prabayar_frames, pengecekan_frames, suspect_frames = [], [], [], []

    for f in by_source[SourceType.DLPD_PASCABAYAR]:
        df, problems = read_dlpd_pascabayar(f)
        report.add_warnings(problems)
        pascabayar_frames.append(df)

    for f in by_source[SourceType.DLPD_PRABAYAR]:
        df, problems = read_dlpd_prabayar(f)
        report.add_warnings(problems)
        prabayar_frames.append(df)

    for f in by_source[SourceType.PENGECEKAN]:
        df, problems = read_pengecekan(f)
        report.add_warnings(problems)
        pengecekan_frames.append(df)

    for f in by_source[SourceType.SUSPECT_ANEV]:
        df, problems = read_suspect_anev(f)
        report.add_warnings(problems)
        suspect_frames.append(df)

    logger.info("=" * 70)
    logger.info("STEP 3/6 — Validating, cleaning & transforming")

    dlpd_customer = transform_dlpd_customers(pascabayar_frames, prabayar_frames)
    require_non_empty(report, "dlpd_customer", len(dlpd_customer))

    pengecekan = pd.concat(pengecekan_frames, ignore_index=True) if pengecekan_frames else pd.DataFrame()
    if not pengecekan.empty:
        key_cols = [c for c in ("ID_P2TL",) if c in pengecekan.columns]
        if key_cols:
            pengecekan = pengecekan.drop_duplicates(subset=key_cols, keep="last")

    suspect_detail = build_suspect_detail(suspect_frames)
    require_non_empty(report, "suspect_detail", len(suspect_detail))

    logger.info("=" * 70)
    logger.info("STEP 4/6 — Generating summary / dashboard / lookup tables")

    suspect_main = build_suspect_main(suspect_detail)
    suspect_summary = build_suspect_summary(suspect_detail)
    executive_kpis = build_executive_kpis(dlpd_customer, suspect_detail, pengecekan)

    report.log_summary()
    if not report.is_valid:
        logger.error("Validation failed — aborting before write. See errors above.")
        return report

    logger.info("=" * 70)
    logger.info("STEP 5/6 — Writing partitioned datasets to %s", output_dir)

    write_partitioned_dataset(dlpd_customer, output_dir, "dlpd_customer")
    write_partitioned_dataset(pengecekan, output_dir, "pengecekan", month_column="MONTH_KEY")
    write_partitioned_dataset(suspect_detail, output_dir, "suspect_detail")
    write_partitioned_dataset(suspect_main, output_dir, "suspect_main")
    write_partitioned_dataset(suspect_summary, output_dir, "suspect_summary")
    write_partitioned_dataset(executive_kpis, output_dir, "executive_kpis")

    logger.info("=" * 70)
    logger.info("STEP 6/6 — Done. Commit & push %s to GitHub for the dashboard to pick up.", output_dir)

    return report


def build_executive_kpis(
    dlpd_customer: pd.DataFrame,
    suspect_detail: pd.DataFrame,
    pengecekan: pd.DataFrame,
) -> pd.DataFrame:
    """One row per month with the KPI-card numbers the Executive
    Dashboard reads directly (no on-request aggregation needed)."""
    months = set()
    for df in (dlpd_customer, suspect_detail, pengecekan):
        if "MONTH_KEY" in df.columns:
            months |= set(df["MONTH_KEY"].dropna().unique())

    rows = []
    for month in sorted(months):
        dlpd_month = dlpd_customer[dlpd_customer.get("MONTH_KEY") == month] if "MONTH_KEY" in dlpd_customer.columns else pd.DataFrame()
        suspect_month = suspect_detail[suspect_detail.get("MONTH_KEY") == month] if "MONTH_KEY" in suspect_detail.columns else pd.DataFrame()
        pengecekan_month = pengecekan[pengecekan.get("MONTH_KEY") == month] if "MONTH_KEY" in pengecekan.columns else pd.DataFrame()

        total_customers = dlpd_month["IDPEL"].nunique() if "IDPEL" in dlpd_month.columns else 0
        total_suspects = suspect_month["LOCATION_CODE"].nunique() if "LOCATION_CODE" in suspect_month.columns else 0
        total_inspected = pengecekan_month["IDPEL"].nunique() if "IDPEL" in pengecekan_month.columns else 0

        # "Findings" = inspections whose DLPD result indicates an actual
        # anomaly (DLPD column present and non-zero/non-empty).
        total_findings = 0
        if "DLPD" in pengecekan_month.columns:
            total_findings = int(
                pengecekan_month["DLPD"].apply(
                    lambda v: str(v).strip().upper() not in ("", "0", "NAN", "NONE", "NORMAL")
                ).sum()
            )
        total_normal = max(total_inspected - total_findings, 0)
        remaining_inspection = max(total_suspects - total_inspected, 0)
        progress = round((total_inspected / total_suspects * 100), 2) if total_suspects else 0.0
        hit_rate = round((total_findings / total_inspected * 100), 2) if total_inspected else 0.0

        rows.append(
            {
                "MONTH_KEY": month,
                "TOTAL_CUSTOMERS": total_customers,
                "TOTAL_SUSPECTS": total_suspects,
                "TOTAL_NORMAL": total_normal,
                "TOTAL_FINDINGS": total_findings,
                "REMAINING_INSPECTION": remaining_inspection,
                "PROGRESS_PCT": progress,
                "HIT_RATE_PCT": hit_rate,
            }
        )

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="PLN Analytics Platform ETL")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    report = run(args.input_dir, args.output_dir)
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
