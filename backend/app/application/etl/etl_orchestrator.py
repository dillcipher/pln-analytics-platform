from __future__ import annotations

import json
import logging
import os
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
    """
    Main ETL Coordinator.

    Flow
    ----
    Upload
        ↓
    Read Manifest
        ↓
    Group Files
        ↓
    Separate fixed coordinate masters
        ↓
    Build CUSTOMER_LOCATION coordinate master
        ↓
    Merge monthly datasets
        ↓
    Enrich DLPD with coordinates
        ↓
    Export Parquet
        ↓
    Update Registry
        ↓
    Refresh Warehouse
        ↓
    Finished


    Coordinate architecture
    ------------------------
    TO_PRABAYAR.xlsx and TO_PASCABAYAR.xlsx are fixed coordinate
    master files.

    They:

    - have month=None;
    - are never exported as customer_location_None.parquet;
    - are used to build CUSTOMER_LOCATION for every business month;
    - are the authoritative coordinate source;
    - are joined to DLPD using IDPEL.

    IMPORTANT:

    CUSTOMER_LOCATION must be created BEFORE DLPD is processed.

    Therefore the orchestrator intentionally uses two phases:

        PHASE 1
            Build customer_location_<month>.parquet

        PHASE 2
            Process DLPD / ANEV / PENGECEKAN / other datasets

    This guarantees that MonthlyMerger._enrich_with_coordinates()
    can load the coordinate master when processing DLPD.
    """

    OUTPUT_DIR = PARQUET

    # ==========================================================
    # FIXED COORDINATE MASTER FILES
    # ==========================================================

    COORDINATE_MASTER_FILES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    # ==========================================================
    # HELPERS
    # ==========================================================

    @classmethod
    def _normalize_filename(
        cls,
        filename: str,
    ) -> str:
        """
        Normalize filename for reliable comparison.
        """

        name = (
            Path(filename)
            .name
            .lower()
            .strip()
        )

        name = name.replace(
            "-",
            "_",
        )

        name = name.replace(
            " ",
            "_",
        )

        while "__" in name:
            name = name.replace(
                "__",
                "_",
            )

        return name

    # ==========================================================

    @classmethod
    def _is_coordinate_master(
        cls,
        filename: str,
    ) -> bool:
        """
        Return True for:

            TO_PRABAYAR.xlsx
            TO_PASCABAYAR.xlsx
        """

        return (
            cls._normalize_filename(
                filename,
            )
            in cls.COORDINATE_MASTER_FILES
        )

    # ==========================================================

    @classmethod
    def _is_valid_file(
        cls,
        file_record: dict,
    ) -> bool:
        """
        Check whether a manifest file is eligible for ETL.

        Validation states:

            PASSED
                File was already validated during upload.

            PENDING
                File came through the large chunked-upload path.

                Large chunked uploads intentionally skip expensive
                Excel inspection during assembly so that a 700+ MB
                workbook does not block the HTTP request.

                The actual DLPD month resolution and dataset
                processing still happen during ETL.

        Therefore PENDING must be accepted here.
        """

        validation = file_record.get(
            "validation",
        )

        filename = file_record.get(
            "filename",
        )

        return (
            validation in {
                "PASSED",
                "PENDING",
            }
            and bool(filename)
        )

    # ==========================================================

    @classmethod
    def _build_paths(
        cls,
        job_folder: Path,
        files: list[dict],
    ) -> list[Path]:
        """
        Convert manifest records into job-local paths.
        """

        return [
            job_folder / file_record["filename"]
            for file_record in files
        ]

    # ==========================================================
    # GET CUSTOMER LOCATION MONTHS
    # ==========================================================

    @classmethod
    def _get_customer_location_months(
        cls,
        grouped: dict,
    ) -> set[str]:
        """
        Return all business months represented by monthly
        CUSTOMER_LOCATION files.

        Fixed TO masters have month=None and are ignored.
        """

        months: set[str] = set()

        for (
            dataset,
            month,
        ), files in grouped.items():

            if dataset != "CUSTOMER_LOCATION":
                continue

            if month is None:
                continue

            valid_files = [
                file_record
                for file_record in files
                if cls._is_valid_file(
                    file_record,
                )
            ]

            if valid_files:
                months.add(
                    str(month),
                )

        return months

    # ==========================================================
    # GET BUSINESS MONTHS
    # ==========================================================

    @classmethod
    def _get_business_months(
        cls,
        grouped: dict,
    ) -> list[str]:
        """
        Return all non-null business months.

        These months can originate from:

            ANEV
            DLPD_PASCABAYAR
            DLPD_PRABAYAR
            CUSTOMER_LOCATION
            other monthly datasets
        """

        months = {
            str(month)
            for (
                _dataset,
                month,
            ) in grouped.keys()
            if month is not None
        }

        return sorted(months)

    # ==========================================================
    # GET DLPD BUSINESS MONTHS
    # ==========================================================

    @classmethod
    def _resolve_dlpd_month_cache(
        cls,
        grouped: dict,
        job_folder: Path,
    ) -> dict[str, set[str]]:
        """
        Resolve DLPD business months once per source file.

        A single DLPD workbook may contain records for multiple
        business months. MonthResolver therefore inspects the actual
        workbook and returns every month represented by its rows.

        The result is cached by filename so the same workbook is not
        read a second time later by ``_expand_processing_groups``.
        """

        month_cache: dict[str, set[str]] = {}

        for (
            dataset,
            _group_month,
        ), files in grouped.items():

            if dataset not in {
                "DLPD_PASCABAYAR",
                "DLPD_PRABAYAR",
            }:
                continue

            valid_files = [
                file_record
                for file_record in files
                if cls._is_valid_file(
                    file_record,
                )
            ]

            for file_record in valid_files:
                filename = file_record.get("filename")

                if not filename:
                    continue

                # A filename can appear in more than one manifest group.
                # Resolve it only once.
                if filename in month_cache:
                    continue

                path = job_folder / filename

                if not path.exists():
                    logger.warning(
                        "DLPD file not found while resolving months: %s",
                        path,
                    )
                    month_cache[filename] = set()
                    continue

                logger.info(
                    "RESOLVING DLPD MONTHS | %s",
                    path.name,
                )

                try:
                    resolved = MonthResolver.resolve_months(
                        path,
                    )
                except Exception:
                    logger.exception(
                        "DLPD MONTH RESOLUTION FAILED | %s",
                        path,
                    )
                    raise

                normalized = {
                    str(month)
                    for month in resolved
                    if month
                }

                month_cache[filename] = normalized

                logger.info(
                    "DLPD MONTH RESOLUTION | %s -> %s",
                    path.name,
                    sorted(normalized),
                )

        return month_cache

    # ==========================================================

    @classmethod
    def _get_dlpd_months(
        cls,
        grouped: dict,
        job_folder: Path,
    ) -> set[str]:
        """
        Return the union of all months resolved from DLPD files.

        This compatibility helper delegates to the per-file cache so
        callers still receive the original ``set[str]`` contract while
        avoiding duplicate workbook resolution inside a single call.
        """

        cache = cls._resolve_dlpd_month_cache(
            grouped=grouped,
            job_folder=job_folder,
        )

        months: set[str] = set()

        for resolved in cache.values():
            months.update(resolved)

        return months

    # ==========================================================
    # EXPAND PROCESSING GROUPS
    # ==========================================================

    @classmethod
    def _expand_processing_groups(
        cls,
        grouped: dict,
        job_folder: Path,
        dlpd_month_cache: dict[str, set[str]] | None = None,
    ) -> list[
        tuple[
            str,
            str | None,
            list[dict],
        ]
    ]:
        """
        Expand DLPD groups into one processing group per actual
        business month.

        Example:

            one DLPD_PASCABAYAR file
                -> 202601
                -> 202602
                -> ...
                -> 202607

        The same source file can therefore be supplied to
        MonthlyMerger for each target month.

        MonthlyMerger is responsible for filtering rows to that
        target MONTH before exporting the parquet.

        ``dlpd_month_cache`` contains the result of the initial DLPD
        month-resolution pass. Reusing it is important for large
        workbooks because MonthResolver reads the Excel file.

        Non-DLPD datasets retain the original grouping behavior.
        """

        expanded: list[
            tuple[
                str,
                str | None,
                list[dict],
            ]
        ] = []

        for (
            dataset,
            group_month,
        ), files in grouped.items():

            valid_files = [
                file_record
                for file_record in files
                if cls._is_valid_file(
                    file_record,
                )
            ]

            if not valid_files:
                expanded.append(
                    (
                        dataset,
                        group_month,
                        files,
                    )
                )
                continue

            if dataset not in {
                "DLPD_PASCABAYAR",
                "DLPD_PRABAYAR",
            }:
                expanded.append(
                    (
                        dataset,
                        group_month,
                        valid_files,
                    )
                )
                continue

            resolved_months: set[str] = set()

            # Reuse the month-resolution result produced during the
            # initial DLPD scan. This prevents reading the same large
            # workbook twice during one ETL job.
            for file_record in valid_files:

                filename = file_record.get("filename")

                if not filename:
                    continue

                if dlpd_month_cache is not None:
                    months = dlpd_month_cache.get(
                        filename,
                        set(),
                    )
                else:
                    # Backward-compatible fallback for callers that
                    # invoke this helper directly without a cache.
                    path = job_folder / filename

                    if not path.exists():
                        logger.warning(
                            "DLPD source file does not exist: %s",
                            path,
                        )
                        continue

                    months = MonthResolver.resolve_months(
                        path,
                    )

                resolved_months.update(
                    str(month)
                    for month in months
                    if month
                )

            # --------------------------------------------------
            # Compatibility fallback.
            #
            # If a DLPD file cannot expose a month from its
            # detailed rows but the manifest already contains a
            # valid month, retain that manifest month.
            # --------------------------------------------------

            if (
                not resolved_months
                and group_month
            ):
                resolved_months.add(
                    str(group_month),
                )

            for month in sorted(
                resolved_months,
            ):

                expanded.append(
                    (
                        dataset,
                        month,
                        valid_files,
                    )
                )

                logger.info(
                    "EXPANDED DLPD GROUP | %s | MONTH=%s | FILES=%s",
                    dataset,
                    month,
                    len(valid_files),
                )

        return expanded

    # ==========================================================
    # COLLECT COORDINATE MASTERS
    # ==========================================================

    @classmethod
    def _collect_coordinate_masters(
        cls,
        grouped: dict,
        job_folder: Path,
    ) -> list[Path]:
        """
        Find validated TO coordinate master files.
        """

        records: list[dict] = []

        for (
            dataset,
            _month,
        ), files in grouped.items():

            if dataset != "CUSTOMER_LOCATION":
                continue

            for file_record in files:

                if not cls._is_valid_file(
                    file_record,
                ):
                    continue

                filename = file_record[
                    "filename"
                ]

                if cls._is_coordinate_master(
                    filename,
                ):
                    records.append(
                        file_record,
                    )

        # ------------------------------------------------------
        # De-duplicate by filename while preserving order.
        # ------------------------------------------------------

        unique_records: list[dict] = []

        seen: set[str] = set()

        for record in records:

            filename = record[
                "filename"
            ]

            if filename in seen:
                continue

            seen.add(filename)

            unique_records.append(
                record,
            )

        paths = cls._build_paths(
            job_folder,
            unique_records,
        )

        logger.info(
            "COORDINATE MASTER FILES : %s",
            [
                path.name
                for path in paths
            ],
        )

        return paths

    # ==========================================================
    # ETL CHECKPOINT / RESUME
    # ==========================================================

    @classmethod
    def _checkpoint_path(
        cls,
        job_folder: Path,
    ) -> Path:
        """
        Return the persistent checkpoint file for this ETL job.

        The checkpoint lives inside the job folder, so it survives an
        application restart as long as the job storage itself survives.
        """
        return job_folder / "etl_checkpoint.json"

    @classmethod
    def _load_checkpoint(
        cls,
        job_folder: Path,
        job_id: str | None,
    ) -> dict:
        """
        Load a previously written ETL checkpoint.

        A checkpoint belonging to another job is ignored. Corrupt
        checkpoints are also ignored so they cannot prevent the ETL
        from starting.
        """
        path = cls._checkpoint_path(
            job_folder,
        )

        if not path.exists():
            return {
                "version": 1,
                "job_id": job_id,
                "phase1_completed": {},
                "phase2_completed": {},
                "warehouse_refreshed": False,
            }

        try:
            with open(
                path,
                encoding="utf-8",
            ) as f:
                checkpoint = json.load(f)

        except Exception:
            logger.exception(
                "ETL CHECKPOINT READ FAILED | %s",
                path,
            )
            return {
                "version": 1,
                "job_id": job_id,
                "phase1_completed": {},
                "phase2_completed": {},
                "warehouse_refreshed": False,
            }

        if checkpoint.get("job_id") != job_id:
            logger.warning(
                "ETL CHECKPOINT JOB MISMATCH | "
                "expected=%s actual=%s | ignoring checkpoint",
                job_id,
                checkpoint.get("job_id"),
            )
            return {
                "version": 1,
                "job_id": job_id,
                "phase1_completed": {},
                "phase2_completed": {},
                "warehouse_refreshed": False,
            }

        checkpoint.setdefault(
            "version",
            1,
        )
        checkpoint.setdefault(
            "phase1_completed",
            {},
        )
        checkpoint.setdefault(
            "phase2_completed",
            {},
        )
        checkpoint.setdefault(
            "warehouse_refreshed",
            False,
        )

        return checkpoint

    @classmethod
    def _save_checkpoint(
        cls,
        job_folder: Path,
        checkpoint: dict,
    ) -> None:
        """
        Persist an ETL checkpoint atomically.

        A temporary file plus os.replace prevents a process restart from
        leaving behind a partially written JSON checkpoint.
        """
        path = cls._checkpoint_path(
            job_folder,
        )
        temporary_path = path.with_suffix(
            ".json.tmp",
        )

        try:
            job_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            with open(
                temporary_path,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    checkpoint,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                f.flush()
                os.fsync(
                    f.fileno(),
                )

            os.replace(
                temporary_path,
                path,
            )

        except Exception:
            logger.exception(
                "ETL CHECKPOINT WRITE FAILED | %s",
                path,
            )

            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except Exception:
                logger.exception(
                    "ETL CHECKPOINT TEMP CLEANUP FAILED | %s",
                    temporary_path,
                )

            # Checkpoint persistence must never turn a successfully
            # processed dataset into a failed ETL job.
            return

    @staticmethod
    def _processing_group_key(
        dataset: str,
        month: str | None,
        files: list[dict],
    ) -> str:
        """
        Build a deterministic checkpoint key for a processing group.
        """
        filenames = sorted(
            str(
                file_record.get(
                    "filename",
                    "",
                )
            )
            for file_record in files
            if file_record.get("filename")
        )

        return json.dumps(
            {
                "dataset": dataset,
                "month": (
                    str(month)
                    if month is not None
                    else None
                ),
                "files": filenames,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

    # ==========================================================
    # PROCESS
    # ==========================================================

    @classmethod
    def process(
        cls,
        job_folder: Path,
    ):

        manifest_file = (
            job_folder
            / "manifest.json"
        )

        if not manifest_file.exists():

            raise FileNotFoundError(
                f"Manifest not found: "
                f"{manifest_file}",
            )

        logger.info(
            "=" * 80,
        )

        logger.info(
            "ETL START",
        )

        logger.info(
            "JOB FOLDER : %s",
            job_folder,
        )

        logger.info(
            "=" * 80,
        )

        # ======================================================
        # READ MANIFEST
        # ======================================================

        with open(
            manifest_file,
            encoding="utf-8",
        ) as f:

            manifest = json.load(f)

        manifest["job_folder"] = str(
            job_folder,
        )

        if not manifest.get("files"):

            raise ValueError(
                "Manifest does not contain "
                "uploaded files.",
            )

        outputs: list[dict] = []

        checkpoint = cls._load_checkpoint(
            job_folder=job_folder,
            job_id=manifest.get("job_id"),
        )

        has_checkpoint = bool(
            checkpoint.get("phase1_completed")
            or checkpoint.get("phase2_completed")
            or checkpoint.get("warehouse_refreshed")
        )

        if has_checkpoint:
            logger.warning(
                "ETL RESUME CHECKPOINT FOUND | JOB=%s",
                manifest.get("job_id"),
            )
        else:
            checkpoint["job_id"] = manifest.get(
                "job_id",
            )
            cls._save_checkpoint(
                job_folder,
                checkpoint,
            )

        try:

            # ==================================================
            # INITIAL JOB STATUS
            # ==================================================

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=20,
                step="GROUPING FILES",
            )

            # ==================================================
            # GROUP FILES
            # ==================================================

            grouped = FileGrouper.group(
                manifest["files"],
            )

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=21,
                step="GROUPING FILES COMPLETED",
            )

            if has_checkpoint:
                JobManager.update(
                    job_folder,
                    status=JobStatus.MERGING,
                    progress=22,
                    step="RESUMING ETL FROM CHECKPOINT",
                )

            if not grouped:

                raise ValueError(
                    "No valid dataset found.",
                )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "GROUP RESULT",
            )

            logger.info(
                "=" * 80,
            )

            for key, value in grouped.items():

                logger.info(
                    "%s --> %s file(s)",
                    key,
                    len(value),
                )

            logger.info(
                "=" * 80,
            )

            # ==================================================
            # COORDINATE MASTER FILES
            # ==================================================

            coordinate_master_paths = (
                cls._collect_coordinate_masters(
                    grouped=grouped,
                    job_folder=job_folder,
                )
            )

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=22,
                step="COLLECTING COORDINATE MASTERS COMPLETED",
            )

            # ==================================================
            # BUSINESS MONTHS
            # ==================================================

            business_months_set = set(
                cls._get_business_months(
                    grouped,
                )
            )

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=23,
                step="RESOLVING BUSINESS MONTHS",
            )

            # --------------------------------------------------
            # Resolve DLPD months ONCE.
            #
            # This is intentionally done before CUSTOMER_LOCATION
            # is built because DLPD may introduce business months
            # that are not present in the manifest grouping.
            # --------------------------------------------------

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=25,
                step="RESOLVING DLPD MONTHS",
            )

            logger.info(
                "DLPD MONTH RESOLUTION START | JOB=%s",
                manifest.get("job_id"),
            )

            dlpd_month_cache = (
                cls._resolve_dlpd_month_cache(
                    grouped=grouped,
                    job_folder=job_folder,
                )
            )

            dlpd_months: set[str] = set()

            for resolved in dlpd_month_cache.values():
                dlpd_months.update(resolved)

            business_months_set.update(
                dlpd_months,
            )

            business_months = sorted(
                business_months_set,
            )

            logger.info(
                "DLPD RESOLVED MONTHS : %s",
                sorted(dlpd_months),
            )

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=28,
                step="DLPD MONTHS RESOLVED",
            )

            logger.info(
                "BUSINESS MONTHS : %s",
                business_months,
            )

            # ==================================================
            # CUSTOMER LOCATION MONTHS
            # ==================================================

            customer_location_months = (
                cls._get_customer_location_months(
                    grouped,
                )
            )

            logger.info(
                "EXISTING CUSTOMER LOCATION MONTHS : %s",
                sorted(
                    customer_location_months,
                ),
            )

            # ==================================================
            # PHASE 1
            # BUILD COORDINATE MASTER FIRST
            # ==================================================

            JobManager.update(
                job_folder,
                status=JobStatus.MERGING,
                progress=30,
                step="BUILDING CUSTOMER LOCATION",
            )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "PHASE 1 - BUILDING CUSTOMER LOCATION",
            )

            logger.info(
                "=" * 80,
            )

            customer_location_outputs: dict[
                str,
                Path,
            ] = {}

            # --------------------------------------------------
            # 1A. Process monthly DIL/CUSTOMER_LOCATION groups.
            # --------------------------------------------------

            customer_location_groups = [
                (
                    month,
                    files,
                )
                for (
                    dataset,
                    month,
                ), files in grouped.items()
                if (
                    dataset
                    == "CUSTOMER_LOCATION"
                    and month is not None
                )
            ]

            # Stable chronological processing.
            customer_location_groups.sort(
                key=lambda item: str(
                    item[0],
                ),
            )

            for (
                month,
                files,
            ) in customer_location_groups:

                valid_files = [
                    file_record
                    for file_record in files
                    if (
                        cls._is_valid_file(
                            file_record,
                        )
                        and not cls._is_coordinate_master(
                            file_record[
                                "filename"
                            ],
                        )
                    )
                ]

                if not valid_files:
                    continue

                monthly_paths = (
                    cls._build_paths(
                        job_folder,
                        valid_files,
                    )
                )

                paths = list(
                    dict.fromkeys(
                        coordinate_master_paths
                        + monthly_paths,
                    )
                )

                logger.info(
                    "-" * 80,
                )

                logger.info(
                    "BUILD CUSTOMER_LOCATION",
                )

                logger.info(
                    "MONTH : %s",
                    month,
                )

                logger.info(
                    "TO MASTER FILES : %s",
                    len(
                        coordinate_master_paths,
                    ),
                )

                logger.info(
                    "DIL FILES : %s",
                    len(
                        monthly_paths,
                    ),
                )

                logger.info(
                    "-" * 80,
                )

                month_key = str(
                    month,
                )

                completed_output = (
                    checkpoint.get(
                        "phase1_completed",
                        {},
                    ).get(
                        month_key,
                    )
                )

                if (
                    completed_output
                    and Path(
                        completed_output,
                    ).exists()
                ):
                    output = Path(
                        completed_output,
                    )

                    logger.info(
                        "RESUME SKIP CUSTOMER_LOCATION | "
                        "MONTH=%s | OUTPUT=%s",
                        month_key,
                        output,
                    )
                else:
                    output = (
                        MonthlyMerger.merge(
                            dataset="CUSTOMER_LOCATION",
                            month=month,
                            files=paths,
                            output_dir=cls.OUTPUT_DIR,
                        )
                    )

                    checkpoint.setdefault(
                        "phase1_completed",
                        {},
                    )[month_key] = str(
                        output,
                    )

                    cls._save_checkpoint(
                        job_folder,
                        checkpoint,
                    )

                customer_location_outputs[
                    str(month)
                ] = output

                customer_location_months.add(
                    str(month),
                )

                logger.info(
                    "CUSTOMER LOCATION CREATED : %s",
                    output,
                )

            # --------------------------------------------------
            # 1B. If TO exists but DIL does not exist for a
            #     business month, build CUSTOMER_LOCATION from
            #     TO masters only.
            # --------------------------------------------------

            if coordinate_master_paths:

                for month in business_months:

                    month_key = str(
                        month,
                    )

                    if (
                        month_key
                        in customer_location_months
                    ):
                        continue

                    logger.info(
                        "-" * 80,
                    )

                    logger.info(
                        "BUILD CUSTOMER_LOCATION "
                        "FROM TO MASTER ONLY",
                    )

                    logger.info(
                        "MONTH : %s",
                        month_key,
                    )

                    logger.info(
                        "MASTER FILES : %s",
                        len(
                            coordinate_master_paths,
                        ),
                    )

                    logger.info(
                        "-" * 80,
                    )

                    completed_output = (
                        checkpoint.get(
                            "phase1_completed",
                            {},
                        ).get(
                            month_key,
                        )
                    )

                    if (
                        completed_output
                        and Path(
                            completed_output,
                        ).exists()
                    ):
                        output = Path(
                            completed_output,
                        )

                        logger.info(
                            "RESUME SKIP CUSTOMER_LOCATION "
                            "FROM MASTER | MONTH=%s | OUTPUT=%s",
                            month_key,
                            output,
                        )
                    else:
                        output = (
                            MonthlyMerger.merge(
                                dataset=(
                                    "CUSTOMER_LOCATION"
                                ),
                                month=month,
                                files=(
                                    coordinate_master_paths
                                ),
                                output_dir=(
                                    cls.OUTPUT_DIR
                                ),
                            )
                        )

                        checkpoint.setdefault(
                            "phase1_completed",
                            {},
                        )[month_key] = str(
                            output,
                        )

                        cls._save_checkpoint(
                            job_folder,
                            checkpoint,
                        )

                    customer_location_outputs[
                        month_key
                    ] = output

                    customer_location_months.add(
                        month_key,
                    )

                    logger.info(
                        "CUSTOMER LOCATION CREATED : %s",
                        output,
                    )

            # ==================================================
            # VERIFY COORDINATE MASTER
            # ==================================================

            if coordinate_master_paths:

                missing_coordinate_months = [
                    month
                    for month in business_months
                    if str(month)
                    not in customer_location_outputs
                    and str(month)
                    not in customer_location_months
                ]

                if missing_coordinate_months:

                    raise RuntimeError(
                        "Coordinate master exists, "
                        "but CUSTOMER_LOCATION could "
                        "not be created for months: "
                        f"{missing_coordinate_months}",
                    )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "PHASE 1 COMPLETED",
            )

            logger.info(
                "CUSTOMER LOCATION MONTHS : %s",
                sorted(
                    customer_location_months,
                ),
            )

            logger.info(
                "=" * 80,
            )

            # ==================================================
            # REGISTRY FOR CUSTOMER LOCATION
            # ==================================================

            for (
                month,
                output,
            ) in customer_location_outputs.items():

                RegistryService.update(
                    dataset=(
                        "CUSTOMER_LOCATION"
                    ),
                    period=month,
                    parquet_file=output,
                )

                logger.info(
                    "REGISTRY UPDATED : "
                    "CUSTOMER_LOCATION / %s",
                    month,
                )

                outputs.append(
                    {
                        "dataset": (
                            "CUSTOMER_LOCATION"
                        ),
                        "month": month,
                        "output": str(
                            output,
                        ),
                    }
                )

            # ==================================================
            # PHASE 2
            # PROCESS ALL OTHER DATASETS
            # ==================================================

            logger.info(
                "=" * 80,
            )

            logger.info(
                "PHASE 2 - PROCESSING DATASETS",
            )

            logger.info(
                "=" * 80,
            )

            processing_groups = (
                cls._expand_processing_groups(
                    grouped=grouped,
                    job_folder=job_folder,
                    dlpd_month_cache=dlpd_month_cache,
                )
            )

            non_customer_groups = [
                (
                    dataset,
                    month,
                    files,
                )
                for (
                    dataset,
                    month,
                    files,
                ) in processing_groups
                if dataset
                != "CUSTOMER_LOCATION"
            ]

            total_groups = len(
                non_customer_groups,
            )

            current_group = 0

            for (
                dataset,
                month,
                files,
            ) in non_customer_groups:

                current_group += 1

                logger.info(
                    "",
                )

                logger.info(
                    "-" * 80,
                )

                logger.info(
                    "PROCESSING DATASET : %s",
                    dataset,
                )

                logger.info(
                    "MONTH : %s",
                    month,
                )

                logger.info(
                    "FILES : %s",
                    len(files),
                )

                logger.info(
                    "-" * 80,
                )

                valid_files = [
                    file_record
                    for file_record in files
                    if cls._is_valid_file(
                        file_record,
                    )
                ]

                if not valid_files:

                    logger.warning(
                        "Skipping dataset %s (%s), "
                        "no valid files.",
                        dataset,
                        month,
                    )

                    continue

                paths = (
                    cls._build_paths(
                        job_folder,
                        valid_files,
                    )
                )

                for path in paths:

                    logger.info(
                        "FILE : %s",
                        path.name,
                    )

                # --------------------------------------------------
                # DLPD safety check
                # --------------------------------------------------

                if (
                    dataset
                    in MonthlyMerger.COORDINATE_DATASETS
                    and month is not None
                    and coordinate_master_paths
                ):

                    month_key = str(
                        month,
                    )

                    coordinate_master_path = (
                        cls.OUTPUT_DIR
                        / "customer_location"
                        / (
                            "customer_location_"
                            f"{month_key}.parquet"
                        )
                    )

                    if not coordinate_master_path.exists():

                        raise RuntimeError(
                            "Cannot process DLPD because "
                            "the coordinate master was not "
                            "created: "
                            f"{coordinate_master_path}",
                        )

                    logger.info(
                        "DLPD coordinate master confirmed : %s",
                        coordinate_master_path,
                    )

                # --------------------------------------------------
                # MERGE
                # --------------------------------------------------

                group_key = cls._processing_group_key(
                    dataset=dataset,
                    month=month,
                    files=valid_files,
                )

                completed_output = (
                    checkpoint.get(
                        "phase2_completed",
                        {},
                    ).get(
                        group_key,
                    )
                )

                if (
                    completed_output
                    and Path(
                        completed_output,
                    ).exists()
                ):
                    output = Path(
                        completed_output,
                    )

                    logger.info(
                        "RESUME SKIP DATASET | "
                        "%s | MONTH=%s | OUTPUT=%s",
                        dataset,
                        month,
                        output,
                    )
                else:
                    output = (
                        MonthlyMerger.merge(
                            dataset=dataset,
                            month=month,
                            files=paths,
                            output_dir=(
                                cls.OUTPUT_DIR
                            ),
                        )
                    )

                    checkpoint.setdefault(
                        "phase2_completed",
                        {},
                    )[group_key] = str(
                        output,
                    )

                    cls._save_checkpoint(
                        job_folder,
                        checkpoint,
                    )

                logger.info(
                    "PARQUET CREATED : %s",
                    output,
                )

                # --------------------------------------------------
                # REGISTRY
                # --------------------------------------------------

                if month is not None:

                    RegistryService.update(
                        dataset=dataset,
                        period=month,
                        parquet_file=output,
                    )

                    logger.info(
                        "REGISTRY UPDATED : %s / %s",
                        dataset,
                        month,
                    )

                outputs.append(
                    {
                        "dataset": dataset,
                        "month": month,
                        "output": str(
                            output,
                        ),
                    }
                )

                # --------------------------------------------------
                # PROGRESS
                # --------------------------------------------------

                progress = (
                    30
                    + int(
                        (
                            current_group
                            / max(
                                total_groups,
                                1,
                            )
                        )
                        * 50
                    )
                )

                JobManager.update(
                    job_folder,
                    status=JobStatus.MERGING,
                    progress=progress,
                    step=(
                        f"MERGING {dataset}"
                    ),
                )

            # ==================================================
            # PHASE 2 COMPLETED
            # ==================================================

            logger.info(
                "=" * 80,
            )

            logger.info(
                "PHASE 2 COMPLETED",
            )

            logger.info(
                "=" * 80,
            )

            # ==================================================
            # WAREHOUSE REFRESH
            # ==================================================

            JobManager.update(
                job_folder,
                status=JobStatus.EXPORTING,
                progress=90,
                step="REFRESHING WAREHOUSE",
            )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "REFRESHING WAREHOUSE",
            )

            logger.info(
                "=" * 80,
            )

            if checkpoint.get(
                "warehouse_refreshed",
                False,
            ):
                logger.info(
                    "RESUME SKIP WAREHOUSE REFRESH | "
                    "checkpoint already marked complete",
                )
            else:
                Warehouse.refresh_tables()

                checkpoint["warehouse_refreshed"] = True

                cls._save_checkpoint(
                    job_folder,
                    checkpoint,
                )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "WAREHOUSE REFRESH COMPLETED",
            )

            logger.info(
                "=" * 80,
            )

            # ==================================================
            # FINISHED
            # ==================================================

            checkpoint.pop(
                "last_error",
                None,
            )
            checkpoint.pop(
                "last_failed_at",
                None,
            )
            checkpoint["finished"] = True

            cls._save_checkpoint(
                job_folder,
                checkpoint,
            )

            JobManager.update(
                job_folder,
                status=JobStatus.FINISHED,
                progress=100,
                step="FINISHED",
            )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "JOB %s FINISHED",
                manifest["job_id"],
            )

            logger.info(
                "=" * 80,
            )

            return {
                "success": True,
                "job_id": manifest[
                    "job_id"
                ],
                "status": (
                    JobStatus.FINISHED.value
                ),
                "outputs": outputs,
            }

        # ======================================================
        # FAILURE
        # ======================================================

        except Exception as exc:

            checkpoint["last_error"] = str(
                exc,
            )
            checkpoint["last_failed_at"] = (
                __import__("datetime").datetime.now().isoformat()
            )

            cls._save_checkpoint(
                job_folder,
                checkpoint,
            )

            JobManager.update(
                job_folder,
                status=JobStatus.FAILED,
                progress=100,
                step="FAILED",
            )

            logger.exception(
                "ETL FAILED FOR JOB %s",
                manifest.get(
                    "job_id",
                ),
            )

            return {
                "success": False,
                "job_id": manifest.get(
                    "job_id",
                ),
                "status": (
                    JobStatus.FAILED.value
                ),
                "error": str(exc),
            }