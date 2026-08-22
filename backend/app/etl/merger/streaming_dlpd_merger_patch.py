"""Memory-safe DLPD XLSX ingestion.

The legacy MonthlyMerger loads the complete workbook into pandas. That is
not viable for the production Pascabayar workbook (~746 MB). This patch keeps
the existing MonthlyMerger for small/non-DLPD datasets and replaces only the
DLPD path with chunked openpyxl -> pandas -> parquet processing.

The first DLPD merge call processes the whole source workbook once and writes
all discovered MONTH partitions. Later per-month calls simply reuse those
partitions, so a multi-month workbook is not reread once per month.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from app.etl.merger.monthly_merger import MonthlyMerger
from app.etl.transformers.dlpd_transformer import DLPDTransformer
from app.etl.validator.validator import DatasetValidator

logger = logging.getLogger(__name__)
_INSTALLED = False
_ORIGINAL_MERGE = MonthlyMerger.merge
_CHUNK_ROWS = 25_000


def _iter_excel_chunks(filepath: Path, dataset: str):
    sheet = DatasetValidator.get_sheet_name(filepath, dataset)
    header = DatasetValidator.detect_header_row(filepath, sheet)

    workbook = load_workbook(filepath, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet]
        header_values = next(
            worksheet.iter_rows(
                min_row=header + 1,
                max_row=header + 1,
                values_only=True,
            ),
            None,
        )
        if not header_values:
            return

        columns = [str(value).strip().upper() if value is not None else "" for value in header_values]
        # Match pandas' practical behaviour for unnamed trailing cells.
        if not any(columns):
            return

        batch: list[tuple] = []
        for row in worksheet.iter_rows(min_row=header + 2, values_only=True):
            batch.append(tuple(row[: len(columns)]))
            if len(batch) >= _CHUNK_ROWS:
                yield pd.DataFrame.from_records(batch, columns=columns)
                batch.clear()

        if batch:
            yield pd.DataFrame.from_records(batch, columns=columns)
    finally:
        workbook.close()


def _normalise_output_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = frame.columns.map(str)
    for column in frame.columns:
        if pd.api.types.is_object_dtype(frame[column]):
            frame[column] = frame[column].fillna("").astype(str).str.strip()
    return frame


def _remove_old_dlpd_outputs(output_dir: Path, dataset: str) -> None:
    folder = output_dir / "dlpd"
    folder.mkdir(parents=True, exist_ok=True)
    prefix = "dlpd_pascabayar_" if dataset == "DLPD_PASCABAYAR" else "dlpd_prabayar_"
    for path in folder.glob(f"{prefix}*.parquet"):
        try:
            path.unlink()
        except OSError:
            logger.warning("Could not remove old DLPD parquet: %s", path)


def _process_all_dlpds(dataset: str, files: list[Path], output_dir: Path) -> dict[str, Path]:
    """Process all source files once and create one or more parquet parts/month."""
    folder = output_dir / "dlpd"
    folder.mkdir(parents=True, exist_ok=True)
    prefix = "dlpd_pascabayar_" if dataset == "DLPD_PASCABAYAR" else "dlpd_prabayar_"

    _remove_old_dlpd_outputs(output_dir, dataset)
    part_numbers: dict[str, int] = {}
    outputs: dict[str, Path] = {}

    coordinate_dir = output_dir / "customer_location"
    coordinate_available = coordinate_dir.exists() and any(coordinate_dir.glob("customer_location_*.parquet"))

    for source in files:
        logger.info("STREAMING DLPD SOURCE | dataset=%s | file=%s | size=%s", dataset, source.name, source.stat().st_size)
        for chunk_number, chunk in enumerate(_iter_excel_chunks(source, dataset), start=1):
            if chunk.empty:
                continue

            chunk = MonthlyMerger._normalize_dataframe_columns(chunk)
            chunk["SOURCE_FILE"] = source.name
            transformed = DLPDTransformer().transform(chunk)

            if transformed.empty or "MONTH" not in transformed.columns:
                continue

            transformed["MONTH"] = (
                transformed["MONTH"]
                .apply(DLPDTransformer._normalize_month_value)
                .fillna("")
                .astype(str)
                .str.strip()
            )

            for month, frame in transformed.groupby("MONTH", sort=True, dropna=False):
                month = str(month).strip()
                if not month:
                    continue

                frame = frame.copy()

                if coordinate_available:
                    frame = MonthlyMerger._enrich_with_coordinates(
                        dataframe=frame,
                        dataset=dataset,
                        month=month,
                        output_dir=output_dir,
                    )
                else:
                    if "KOORDINAT_X" not in frame.columns:
                        frame["KOORDINAT_X"] = pd.NA
                    if "KOORDINAT_Y" not in frame.columns:
                        frame["KOORDINAT_Y"] = pd.NA

                frame = _normalise_output_frame(frame)
                part_numbers[month] = part_numbers.get(month, 0) + 1
                output = folder / f"{prefix}{month}_part{part_numbers[month]:05d}.parquet"
                frame.to_parquet(output, index=False)
                outputs.setdefault(month, output)

                logger.info(
                    "STREAMING DLPD PART WRITTEN | dataset=%s | month=%s | chunk=%s | rows=%s | output=%s",
                    dataset,
                    month,
                    chunk_number,
                    len(frame),
                    output,
                )

    if not outputs:
        raise ValueError(f"Streaming DLPD processing produced no monthly rows for {dataset}.")

    logger.info("STREAMING DLPD COMPLETE | dataset=%s | months=%s", dataset, sorted(outputs))
    return outputs


def _streaming_merge(dataset: str, month: str | None, files: list[Path], output_dir: Path) -> Path:
    if not files:
        raise ValueError(f"No files supplied for dataset '{dataset}'.")

    folder = output_dir / "dlpd"
    prefix = "dlpd_pascabayar_" if dataset == "DLPD_PASCABAYAR" else "dlpd_prabayar_"
    target = DLPDTransformer._normalize_month_value(month) if month is not None else None

    # If a previous call already generated the target partition, do not scan
    # the huge XLSX again. This is what makes multi-month DLPD jobs practical.
    if target:
        existing = sorted(folder.glob(f"{prefix}{target}_part*.parquet"))
        if existing:
            return existing[0]

    outputs = _process_all_dlpds(dataset, files, output_dir)
    if target and target in outputs:
        return outputs[target]
    if target:
        raise ValueError(f"DLPD month {target} was requested but no rows were found in the source workbook.")
    return next(iter(outputs.values()))


def install_streaming_dlpd_merger_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    def patched_merge(dataset: str, month: str | None, files: list[Path], output_dir: Path) -> Path:
        if dataset in MonthlyMerger.COORDINATE_DATASETS:
            return _streaming_merge(dataset, month, files, output_dir)
        return _ORIGINAL_MERGE(dataset, month, files, output_dir)

    MonthlyMerger.merge = staticmethod(patched_merge)
    _INSTALLED = True
    logger.info("Installed memory-safe streaming DLPD merger patch.")
