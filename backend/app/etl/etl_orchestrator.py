from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from app.application.jobs.job_manager import JobManager
from app.application.jobs.job_status import JobStatus
from app.application.registry.registry_service import RegistryService
from app.core.constants import PARQUET
from app.database.warehouse import Warehouse
from app.etl.detector.file_grouper import FileGrouper
from app.etl.detector.month_resolver import MonthResolver
from app.etl.merger.monthly_merger import MonthlyMerger

logger = logging.getLogger(__name__)


class ETLOrchestrator:
    OUTPUT_DIR = PARQUET

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    @classmethod
    def _normalize_filename(cls, filename: str) -> str:
        name = Path(filename).name.lower().strip()
        name = name.replace("-", "_").replace(" ", "_")
        while "__" in name:
            name = name.replace("__", "_")
        return name

    @classmethod
    def _is_coordinate_master(cls, filename: str) -> bool:
        return cls._normalize_filename(filename) in cls.COORDINATE_MASTER_FILES

    @classmethod
    def _is_valid_file(cls, file_record: dict) -> bool:
        validation = file_record.get("validation")
        filename = file_record.get("filename")
        return validation in {"PASSED", "PENDING"} and bool(filename)

    @classmethod
    def _build_paths(cls, job_folder: Path, files: list[dict]) -> list[Path]:
        return [job_folder / file_record["filename"] for file_record in files]

    @classmethod
    def _get_customer_location_months(cls, grouped: dict) -> set[str]:
        months: set[str] = set()
        for (dataset, month), files in grouped.items():
            if dataset != "CUSTOMER_LOCATION" or month is None:
                continue
            if any(cls._is_valid_file(file_record) for file_record in files):
                months.add(str(month))
        return months

    @classmethod
    def _get_business_months(cls, grouped: dict) -> list[str]:
        return sorted({str(month) for (_dataset, month) in grouped if month is not None})

    @classmethod
    def _resolve_dlpd_month_cache(cls, grouped: dict, job_folder: Path) -> dict[str, set[str]]:
        month_cache: dict[str, set[str]] = {}
        for (dataset, group_month), files in grouped.items():
            if dataset not in {"DLPD_PASCABAYAR", "DLPD_PRABAYAR"}:
                continue
            valid_files = [file_record for file_record in files if cls._is_valid_file(file_record)]
            for file_record in valid_files:
                filename = file_record.get("filename")
                if not filename or filename in month_cache:
                    continue
                path = job_folder / filename
                if not path.exists():
                    raise FileNotFoundError(f"DLPD source file not found: {path}")
                logger.info("RESOLVING DLPD MONTHS | %s", path.name)
                resolved = MonthResolver.resolve_months(path)
                normalized = {str(month) for month in resolved if month}
                if not normalized and group_month:
                    normalized.add(str(group_month))
                if not normalized:
                    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])", path.stem)
                    if match:
                        normalized.add(f"{match.group(1)}{match.group(2)}")
                if not normalized:
                    raise RuntimeError(
                        "DLPD business month could not be resolved for "
                        f"{path.name}; refusing to mark ETL successful."
                    )
                month_cache[filename] = normalized
                logger.info("DLPD MONTH RESOLUTION | %s -> %s", path.name, sorted(normalized))
        return month_cache

    @classmethod
    def _get_dlpd_months(cls, grouped: dict, job_folder: Path) -> set[str]:
        months: set[str] = set()
        for resolved in cls._resolve_dlpd_month_cache(grouped, job_folder).values():
            months.update(resolved)
        return months

    @classmethod
    def _expand_processing_groups(cls, grouped: dict, job_folder: Path, dlpd_month_cache: dict[str, set[str]] | None = None):
        expanded = []
        for (dataset, group_month), files in grouped.items():
            valid_files = [file_record for file_record in files if cls._is_valid_file(file_record)]
            if not valid_files:
                continue
            if dataset not in {"DLPD_PASCABAYAR", "DLPD_PRABAYAR"}:
                expanded.append((dataset, group_month, valid_files))
                continue
            resolved_months: set[str] = set()
            for file_record in valid_files:
                filename = file_record.get("filename")
                if not filename:
                    continue
                months = (dlpd_month_cache or {}).get(filename, set())
                resolved_months.update(str(month) for month in months if month)
            if not resolved_months and group_month:
                resolved_months.add(str(group_month))
            if not resolved_months:
                raise RuntimeError(
                    f"Phase 2 produced zero months for {dataset}; ETL cannot succeed."
                )
            for month in sorted(resolved_months):
                expanded.append((dataset, month, valid_files))
                logger.info("EXPANDED DLPD GROUP | %s | MONTH=%s | FILES=%s", dataset, month, len(valid_files))
        return expanded

    @classmethod
    def _collect_coordinate_masters(cls, grouped: dict, job_folder: Path) -> list[Path]:
        records = []
        for (dataset, _month), files in grouped.items():
            if dataset != "CUSTOMER_LOCATION":
                continue
            for file_record in files:
                if cls._is_valid_file(file_record) and cls._is_coordinate_master(file_record["filename"]):
                    records.append(file_record)
        unique_records = []
        seen: set[str] = set()
        for record in records:
            filename = record["filename"]
            if filename in seen:
                continue
            seen.add(filename)
            unique_records.append(record)
        paths = cls._build_paths(job_folder, unique_records)
        logger.info("COORDINATE MASTER FILES : %s", [path.name for path in paths])
        return paths

    @classmethod
    def _checkpoint_path(cls, job_folder: Path) -> Path:
        return job_folder / "etl_checkpoint.json"

    @classmethod
    def _load_checkpoint(cls, job_folder: Path, job_id: str | None) -> dict:
        path = cls._checkpoint_path(job_folder)
        if not path.exists():
            return {"version": 1, "job_id": job_id, "phase1_completed": {}, "phase2_completed": {}, "warehouse_refreshed": False}
        try:
            with open(path, encoding="utf-8") as f:
                checkpoint = json.load(f)
        except Exception:
            logger.exception("ETL CHECKPOINT READ FAILED | %s", path)
            return {"version": 1, "job_id": job_id, "phase1_completed": {}, "phase2_completed": {}, "warehouse_refreshed": False}
        if checkpoint.get("job_id") != job_id:
            return {"version": 1, "job_id": job_id, "phase1_completed": {}, "phase2_completed": {}, "warehouse_refreshed": False}
        checkpoint.setdefault("version", 1)
        checkpoint.setdefault("phase1_completed", {})
        checkpoint.setdefault("phase2_completed", {})
        checkpoint.setdefault("warehouse_refreshed", False)
        return checkpoint

    @classmethod
    def _save_checkpoint(cls, job_folder: Path, checkpoint: dict) -> None:
        path = cls._checkpoint_path(job_folder)
        temporary_path = path.with_suffix(".json.tmp")
        try:
            job_folder.mkdir(parents=True, exist_ok=True)
            with open(temporary_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, path)
        except Exception:
            logger.exception("ETL CHECKPOINT WRITE FAILED | %s", path)
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except Exception:
                logger.exception("ETL CHECKPOINT TEMP CLEANUP FAILED | %s", temporary_path)

    @staticmethod
    def _processing_group_key(dataset: str, month: str | None, files: list[dict]) -> str:
        filenames = sorted(str(file_record.get("filename", "")) for file_record in files if file_record.get("filename"))
        return json.dumps({"dataset": dataset, "month": str(month) if month is not None else None, "files": filenames}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def process(cls, job_folder: Path):
        manifest_file = job_folder / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_file}")
        logger.info("=" * 80)
        logger.info("ETL START")
        logger.info("JOB FOLDER : %s", job_folder)
        logger.info("=" * 80)
        with open(manifest_file, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["job_folder"] = str(job_folder)
        if not manifest.get("files"):
            raise ValueError("Manifest does not contain uploaded files.")
        outputs: list[dict] = []
        checkpoint = cls._load_checkpoint(job_folder, manifest.get("job_id"))
        has_checkpoint = bool(checkpoint.get("phase1_completed") or checkpoint.get("phase2_completed") or checkpoint.get("warehouse_refreshed"))
        if has_checkpoint:
            logger.warning("ETL RESUME CHECKPOINT FOUND | JOB=%s", manifest.get("job_id"))
        else:
            checkpoint["job_id"] = manifest.get("job_id")
            cls._save_checkpoint(job_folder, checkpoint)
        try:
            JobManager.update(job_folder, status=JobStatus.MERGING, progress=20, step="GROUPING FILES")
            grouped = FileGrouper.group(manifest["files"])
            JobManager.update(job_folder, status=JobStatus.MERGING, progress=21, step="GROUPING FILES COMPLETED")
            if not grouped:
                raise ValueError("No valid dataset found.")
            for key, value in grouped.items():
                logger.info("%s --> %s file(s)", key, len(value))
            coordinate_master_paths = cls._collect_coordinate_masters(grouped, job_folder)
            business_months_set = set(cls._get_business_months(grouped))
            JobManager.update(job_folder, status=JobStatus.MERGING, progress=25, step="RESOLVING DLPD MONTHS")
            dlpd_month_cache = cls._resolve_dlpd_month_cache(grouped, job_folder)
            dlpd_months = set().union(*dlpd_month_cache.values()) if dlpd_month_cache else set()
            business_months_set.update(dlpd_months)
            business_months = sorted(business_months_set)
            logger.info("DLPD RESOLVED MONTHS : %s", sorted(dlpd_months))
            logger.info("BUSINESS MONTHS : %s", business_months)

            customer_location_outputs: dict[str, Path] = {}
            customer_location_months = cls._get_customer_location_months(grouped)
            customer_location_groups = [
                (month, files) for (dataset, month), files in grouped.items()
                if dataset == "CUSTOMER_LOCATION" and month is not None
            ]
            customer_location_groups.sort(key=lambda item: str(item[0]))

            for month, files in customer_location_groups:
                valid_files = [f for f in files if cls._is_valid_file(f) and not cls._is_coordinate_master(f["filename"])]
                if not valid_files:
                    continue
                monthly_paths = cls._build_paths(job_folder, valid_files)
                paths = list(dict.fromkeys(coordinate_master_paths + monthly_paths))
                month_key = str(month)
                completed_output = checkpoint.get("phase1_completed", {}).get(month_key)
                if completed_output and Path(completed_output).exists() and Path(completed_output).stat().st_size > 0:
                    output = Path(completed_output)
                else:
                    output = MonthlyMerger.merge("CUSTOMER_LOCATION", month, paths, cls.OUTPUT_DIR)
                    checkpoint.setdefault("phase1_completed", {})[month_key] = str(output)
                    cls._save_checkpoint(job_folder, checkpoint)
                customer_location_outputs[month_key] = output
                customer_location_months.add(month_key)

            if coordinate_master_paths:
                for month in business_months:
                    month_key = str(month)
                    if month_key in customer_location_months:
                        continue
                    completed_output = checkpoint.get("phase1_completed", {}).get(month_key)
                    if completed_output and Path(completed_output).exists() and Path(completed_output).stat().st_size > 0:
                        output = Path(completed_output)
                    else:
                        output = MonthlyMerger.merge("CUSTOMER_LOCATION", month, coordinate_master_paths, cls.OUTPUT_DIR)
                        checkpoint.setdefault("phase1_completed", {})[month_key] = str(output)
                        cls._save_checkpoint(job_folder, checkpoint)
                    customer_location_outputs[month_key] = output
                    customer_location_months.add(month_key)

            if coordinate_master_paths:
                missing = [m for m in business_months if str(m) not in customer_location_outputs and str(m) not in customer_location_months]
                if missing:
                    raise RuntimeError(f"Coordinate master exists, but CUSTOMER_LOCATION could not be created for months: {missing}")

            for month, output in customer_location_outputs.items():
                RegistryService.update("CUSTOMER_LOCATION", month, output)
                outputs.append({"dataset": "CUSTOMER_LOCATION", "month": month, "output": str(output)})

            logger.info("=" * 80)
            logger.info("PHASE 2 - PROCESSING DATASETS")
            logger.info("=" * 80)
            processing_groups = cls._expand_processing_groups(grouped, job_folder, dlpd_month_cache)
            non_customer_groups = [(dataset, month, files) for dataset, month, files in processing_groups if dataset != "CUSTOMER_LOCATION"]
            logger.info("PHASE 2 GROUPS | total=%s | groups=%s", len(non_customer_groups), [(d, m, len(f)) for d, m, f in non_customer_groups])
            expected_phase2_datasets = {dataset for (dataset, _month), files in grouped.items() if dataset != "CUSTOMER_LOCATION" and any(cls._is_valid_file(record) for record in files)}
            if expected_phase2_datasets and not non_customer_groups:
                raise RuntimeError(f"PHASE 2 produced zero processing groups for valid datasets: {sorted(expected_phase2_datasets)}")
            if any(dataset in {"DLPD_PRABAYAR", "DLPD_PASCABAYAR"} for dataset, _, _ in non_customer_groups) and not coordinate_master_paths:
                logger.warning("No coordinate master uploaded; DLPD will still be processed with coordinates left NULL.")

            current_group = 0
            for dataset, month, files in non_customer_groups:
                current_group += 1
                valid_files = [f for f in files if cls._is_valid_file(f)]
                if not valid_files:
                    continue
                paths = cls._build_paths(job_folder, valid_files)
                if dataset in MonthlyMerger.COORDINATE_DATASETS and month is not None and coordinate_master_paths:
                    coordinate_master_path = cls.OUTPUT_DIR / "customer_location" / f"customer_location_{month}.parquet"
                    if not coordinate_master_path.exists():
                        raise RuntimeError(f"Cannot process DLPD because the coordinate master was not created: {coordinate_master_path}")
                group_key = cls._processing_group_key(dataset, month, valid_files)
                completed_output = checkpoint.get("phase2_completed", {}).get(group_key)
                if completed_output and Path(completed_output).exists() and Path(completed_output).stat().st_size > 0:
                    output = Path(completed_output)
                else:
                    output = MonthlyMerger.merge(dataset, month, paths, cls.OUTPUT_DIR)
                    if not output.exists() or output.stat().st_size == 0:
                        raise RuntimeError(f"ETL produced no parquet output for {dataset}/{month}: {output}")
                    checkpoint.setdefault("phase2_completed", {})[group_key] = str(output)
                    cls._save_checkpoint(job_folder, checkpoint)
                logger.info("PARQUET CREATED : %s", output)
                if month is not None:
                    RegistryService.update(dataset, month, output)
                    outputs.append({"dataset": dataset, "month": month, "output": str(output)})
                JobManager.update(job_folder, status=JobStatus.MERGING, progress=30 + int((current_group / max(len(non_customer_groups), 1)) * 50), step=f"MERGING {dataset}")

            expected_warehouse_datasets = {"DLPD_PRABAYAR", "DLPD_PASCABAYAR"} & expected_phase2_datasets
            produced_warehouse_datasets = {item["dataset"] for item in outputs}
            missing_dlpds = sorted(expected_warehouse_datasets - produced_warehouse_datasets)
            if missing_dlpds:
                raise RuntimeError(f"Required DLPD parquet outputs were not produced: {missing_dlpds}")

            logger.info("PHASE 2 COMPLETED")
            JobManager.update(job_folder, status=JobStatus.EXPORTING, progress=90, step="REFRESHING WAREHOUSE")
            Warehouse.refresh_tables()
            checkpoint["warehouse_refreshed"] = True
            cls._save_checkpoint(job_folder, checkpoint)

            missing_tables = [table for table in expected_warehouse_datasets if not Warehouse.table_exists(table)]
            if missing_tables:
                raise RuntimeError(f"Warehouse refresh did not create required tables: {missing_tables}")

            checkpoint.pop("last_error", None)
            checkpoint.pop("last_failed_at", None)
            checkpoint["finished"] = True
            cls._save_checkpoint(job_folder, checkpoint)
            JobManager.update(job_folder, status=JobStatus.FINISHED, progress=100, step="FINISHED")
            logger.info("JOB %s FINISHED", manifest["job_id"])
            return {"success": True, "job_id": manifest["job_id"], "status": JobStatus.FINISHED.value, "outputs": outputs}
        except Exception as exc:
            checkpoint["last_error"] = str(exc)
            checkpoint["last_failed_at"] = __import__("datetime").datetime.now().isoformat()
            cls._save_checkpoint(job_folder, checkpoint)
            JobManager.update(job_folder, status=JobStatus.FAILED, progress=100, step="FAILED")
            logger.exception("ETL FAILED FOR JOB %s", manifest.get("job_id"))
            return {"success": False, "job_id": manifest.get("job_id"), "status": JobStatus.FAILED.value, "error": str(exc)}
