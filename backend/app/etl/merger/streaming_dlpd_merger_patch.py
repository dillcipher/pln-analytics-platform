"""Memory-safe, restart-safe DLPD XLSX ingestion.

The production DLPD workbooks are large enough that pandas must never
materialise the complete XLSX in memory. This patch keeps the existing
MonthlyMerger for small/non-DLPD datasets and replaces only DLPD processing
with a bounded openpyxl -> pandas -> parquet pipeline.

Design goals:
- bounded memory (small row batches);
- one source scan per DLPD dataset/job;
- preserve the existing first-IDPEL-wins duplicate behaviour across chunks;
- write to a staging directory first so an OOM/crash cannot destroy the last
  good DLPD parquet set;
- publish staged parquet files only after the complete source scan succeeds;
- later per-month merge calls reuse the already-published partitions from the
  same source job instead of rescanning the workbook.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import uuid
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from app.etl.merger.monthly_merger import MonthlyMerger
from app.etl.transformers.dlpd_transformer import DLPDTransformer
from app.etl.validator.validator import DatasetValidator

logger = logging.getLogger(__name__)

_INSTALLED = False
_ORIGINAL_MERGE = MonthlyMerger.merge

# Conservative default for the 500 MB production runtime.
_CHUNK_ROWS = max(
    500,
    int(os.getenv("DLPD_STREAM_CHUNK_ROWS", "5000")),
)

# (dataset, absolute source-file tuple) -> published month -> parquet path
_COMPLETED_RUNS: dict[tuple[str, tuple[str, ...]], dict[str, Path]] = {}


def _source_key(dataset: str, files: list[Path]) -> tuple[str, tuple[str, ...]]:
    return (
        dataset,
        tuple(sorted(str(Path(path).resolve()) for path in files)),
    )


def _iter_excel_chunks(filepath: Path, dataset: str):
    """Yield bounded pandas frames from an XLSX worksheet."""
    filepath = Path(filepath)

    if filepath.suffix.lower() not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        raise ValueError(
            f"Streaming DLPD requires XLSX/XLSM format: {filepath.name}"
        )

    sheet = DatasetValidator.get_sheet_name(filepath, dataset)
    header = DatasetValidator.detect_header_row(filepath, sheet)

    workbook = load_workbook(
        filepath,
        read_only=True,
        data_only=True,
    )

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

        columns = [
            str(value).strip().upper() if value is not None else ""
            for value in header_values
        ]

        if not any(columns):
            return

        batch: list[tuple] = []

        for row in worksheet.iter_rows(
            min_row=header + 2,
            values_only=True,
        ):
            batch.append(tuple(row[: len(columns)]))

            if len(batch) >= _CHUNK_ROWS:
                yield pd.DataFrame.from_records(
                    batch,
                    columns=columns,
                )
                batch.clear()

        if batch:
            yield pd.DataFrame.from_records(
                batch,
                columns=columns,
            )

    finally:
        workbook.close()


def _normalise_output_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep parquet output deterministic and release object-heavy values."""
    frame = frame.copy()
    frame.columns = frame.columns.map(str)

    for column in frame.columns:
        if pd.api.types.is_object_dtype(frame[column]):
            frame[column] = (
                frame[column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

    return frame


def _deduplicate_first_idpel(
    frame: pd.DataFrame,
    seen_db: sqlite3.Connection,
) -> pd.DataFrame:
    """Replicate BaseTransformer's first-IDPEL-wins rule across chunks.

    A Python set containing millions of IDs would itself consume a large
    fraction of the 500 MB runtime. SQLite keeps the seen-ID index on disk.
    """
    if frame.empty or "IDPEL" not in frame.columns:
        return frame

    ids = (
        frame["IDPEL"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    frame = frame.loc[ids.ne("")].copy()
    if frame.empty:
        return frame

    ids = frame["IDPEL"].astype(str).str.strip()
    frame = frame.loc[~ids.duplicated(keep="first")].copy()
    ids = frame["IDPEL"].astype(str).str.strip()

    seen_db.execute("DELETE FROM batch_ids")
    seen_db.executemany(
        "INSERT OR IGNORE INTO batch_ids(idpel) VALUES (?)",
        ((value,) for value in ids.tolist()),
    )

    new_ids = {
        row[0]
        for row in seen_db.execute(
            """
            SELECT b.idpel
            FROM batch_ids AS b
            LEFT JOIN seen_idpel AS s
              ON s.idpel = b.idpel
            WHERE s.idpel IS NULL
            """
        )
    }

    if not new_ids:
        return frame.iloc[0:0].copy()

    seen_db.executemany(
        "INSERT INTO seen_idpel(idpel) VALUES (?)",
        ((value,) for value in new_ids),
    )
    seen_db.commit()

    return frame.loc[ids.isin(new_ids)].copy()


def _publish_staged_outputs(
    output_dir: Path,
    dataset: str,
    staged_files: list[Path],
) -> dict[str, Path]:
    """Publish a complete staged DLPD result set."""
    folder = output_dir / "dlpd"
    folder.mkdir(parents=True, exist_ok=True)

    prefix = (
        "dlpd_pascabayar_"
        if dataset == "DLPD_PASCABAYAR"
        else "dlpd_prabayar_"
    )

    prepared: list[tuple[Path, Path]] = []

    # Copy to hidden names first. Hidden names do not match the warehouse
    # glob, so an incomplete publish can never be queried as production data.
    for staged in staged_files:
        final = folder / staged.name
        hidden = folder / f".{staged.name}.new"
        shutil.copy2(staged, hidden)
        prepared.append((hidden, final))

    # Do not remove the previous good dataset until every new part is safely
    # present on the production filesystem.
    for old in folder.glob(f"{prefix}*.parquet"):
        try:
            old.unlink()
        except OSError as exc:
            raise RuntimeError(
                f"Could not replace old DLPD parquet {old}: {exc}"
            ) from exc

    published: dict[str, Path] = {}

    try:
        for hidden, final in prepared:
            os.replace(hidden, final)
            stem_parts = final.stem.split("_")
            month = (
                stem_parts[-2]
                if len(stem_parts) >= 3 and stem_parts[-1].startswith("part")
                else ""
            )
            if month:
                published.setdefault(month, final)
    except Exception:
        for hidden, _final in prepared:
            hidden.unlink(missing_ok=True)
        raise

    if not published:
        raise RuntimeError("DLPD publish completed but no monthly partitions were detected.")

    logger.info(
        "DLPD PUBLISH COMPLETE | dataset=%s | months=%s | files=%s",
        dataset,
        sorted(published),
        len(prepared),
    )
    return published


def _process_all_dlpds(
    dataset: str,
    files: list[Path],
    output_dir: Path,
) -> dict[str, Path]:
    """Scan all DLPD sources once and publish monthly parquet partitions."""
    if not files:
        raise ValueError(
            f"No files supplied for dataset '{dataset}'."
        )

    output_dir = Path(output_dir)
    staging_root = output_dir / ".dlpd_stream_staging"
    staging_dir = staging_root / f"{dataset.lower()}_{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    prefix = (
        "dlpd_pascabayar_"
        if dataset == "DLPD_PASCABAYAR"
        else "dlpd_prabayar_"
    )

    part_numbers: dict[str, int] = {}
    staged_files: list[Path] = []

    coordinate_dir = output_dir / "customer_location"
    coordinate_available = (
        coordinate_dir.exists()
        and any(coordinate_dir.glob("customer_location_*.parquet"))
    )

    seen_db = sqlite3.connect(
        staging_dir / "seen_idpel.sqlite3"
    )

    try:
        seen_db.execute(
            "CREATE TABLE seen_idpel (idpel TEXT PRIMARY KEY)"
        )
        seen_db.execute(
            "CREATE TEMP TABLE batch_ids (idpel TEXT PRIMARY KEY)"
        )
        seen_db.commit()

        for source in files:
            source = Path(source)
            logger.info(
                "STREAMING DLPD SOURCE | dataset=%s | file=%s | size=%s | chunk_rows=%s",
                dataset,
                source.name,
                source.stat().st_size,
                _CHUNK_ROWS,
            )

            for chunk_number, chunk in enumerate(
                _iter_excel_chunks(source, dataset),
                start=1,
            ):
                if chunk.empty:
                    continue

                chunk = MonthlyMerger._normalize_dataframe_columns(chunk)
                chunk["SOURCE_FILE"] = source.name

                chunk = _deduplicate_first_idpel(
                    chunk,
                    seen_db,
                )
                if chunk.empty:
                    continue

                transformed = DLPDTransformer().transform(chunk)

                if transformed.empty or "MONTH" not in transformed.columns:
                    continue

                transformed["MONTH"] = (
                    transformed["MONTH"]
                    .apply(
                        DLPDTransformer._normalize_month_value
                    )
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

                for month, frame in transformed.groupby(
                    "MONTH",
                    sort=True,
                    dropna=False,
                ):
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

                    part_numbers[month] = (
                        part_numbers.get(month, 0) + 1
                    )

                    output = (
                        staging_dir
                        / f"{prefix}{month}_part"
                        f"{part_numbers[month]:05d}.parquet"
                    )

                    frame.to_parquet(
                        output,
                        index=False,
                    )
                    staged_files.append(output)

                    logger.info(
                        "STREAMING DLPD PART WRITTEN | dataset=%s | month=%s | chunk=%s | rows=%s",
                        dataset,
                        month,
                        chunk_number,
                        len(frame),
                    )

        if not staged_files:
            raise ValueError(
                "Streaming DLPD processing produced no monthly rows "
                f"for {dataset}."
            )

        outputs = _publish_staged_outputs(
            output_dir=output_dir,
            dataset=dataset,
            staged_files=staged_files,
        )

        logger.info(
            "STREAMING DLPD COMPLETE | dataset=%s | months=%s | parts=%s",
            dataset,
            sorted(outputs),
            len(staged_files),
        )
        return outputs

    finally:
        seen_db.close()
        shutil.rmtree(
            staging_dir,
            ignore_errors=True,
        )
        try:
            staging_root.rmdir()
        except OSError:
            pass


def _streaming_merge(
    dataset: str,
    month: str | None,
    files: list[Path],
    output_dir: Path,
) -> Path:
    if not files:
        raise ValueError(
            f"No files supplied for dataset '{dataset}'."
        )

    key = _source_key(dataset, files)
    target = (
        DLPDTransformer._normalize_month_value(month)
        if month is not None
        else None
    )

    outputs = _COMPLETED_RUNS.get(key)
    if outputs is None:
        outputs = _process_all_dlpds(
            dataset=dataset,
            files=files,
            output_dir=output_dir,
        )
        _COMPLETED_RUNS[key] = outputs

    if target:
        output = outputs.get(target)
        if output is None:
            raise ValueError(
                f"DLPD month {target} was requested but no rows were found."
            )
        return output

    return next(iter(outputs.values()))


def install_streaming_dlpd_merger_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    def patched_merge(
        dataset: str,
        month: str | None,
        files: list[Path],
        output_dir: Path,
    ) -> Path:
        if dataset in MonthlyMerger.COORDINATE_DATASETS:
            return _streaming_merge(
                dataset,
                month,
                files,
                output_dir,
            )

        return _ORIGINAL_MERGE(
            dataset,
            month,
            files,
            output_dir,
        )

    MonthlyMerger.merge = staticmethod(patched_merge)
    _INSTALLED = True
    logger.info(
        "Installed restart-safe memory-bounded DLPD merger patch | chunk_rows=%s",
        _CHUNK_ROWS,
    )
