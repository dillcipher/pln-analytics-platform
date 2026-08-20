from __future__ import annotations

import logging
from pathlib import Path

from app.core.constants import PARQUET
from app.etl.detector.file_grouper import FileGrouper
from app.etl.detector.detector import FileDetector
from app.etl.merger.monthly_merger import MonthlyMerger


logger = logging.getLogger(__name__)


class ETLPipeline:
    """
    ETL pipeline for legacy/direct ETL callers.

    Coordinate master rules
    -----------------------
    TO_PRABAYAR.xlsx and TO_PASCABAYAR.xlsx are fixed coordinate
    masters. They are CUSTOMER_LOCATION sources with month=None.

    They must NEVER be written as:

        customer_location_None.parquet

    Instead, when at least one business month exists, the coordinate
    masters are included as the authoritative coordinate source for
    each CUSTOMER_LOCATION monthly merge.

    Month ownership remains with MonthResolver. This class never
    invents or changes a business month.
    """

    OUTPUT = PARQUET

    # ==========================================================
    # COORDINATE MASTER DETECTION
    # ==========================================================

    @staticmethod
    def _is_coordinate_master_file(
        filename: str | Path,
    ) -> bool:
        """
        Detect the two fixed TO coordinate masters.

        Use the same normalization convention as FileDetector so
        this pipeline cannot disagree with the upload detector.
        """

        return FileDetector.is_coordinate_master(
            Path(filename),
        )

    # ==========================================================
    # MANIFEST PATH
    # ==========================================================

    @staticmethod
    def _manifest_paths(
        job_folder: str | Path,
        files: list[dict],
    ) -> list[Path]:
        """
        Convert manifest records into job-folder paths.

        Only records with a filename are converted. Invalid manifest
        records are ignored here and are logged by the caller.
        """

        paths: list[Path] = []

        for item in files:
            filename = item.get("filename")

            if not filename:
                continue

            paths.append(
                Path(job_folder) / filename
            )

        return paths

    # ==========================================================
    # VALID FILES
    # ==========================================================

    @staticmethod
    def _valid_files(
        files: list[dict],
    ) -> list[dict]:
        """
        Keep only files that passed upload validation.

        Older manifests may not contain validation metadata, so those
        records are retained for backward compatibility.
        """

        valid: list[dict] = []

        for item in files:
            validation = item.get("validation")

            if validation in (
                None,
                "",
                "PASSED",
            ):
                valid.append(item)

        return valid

    # ==========================================================
    # PROCESS
    # ==========================================================

    @classmethod
    def process(
        cls,
        manifest: dict,
    ) -> list[str]:
        """
        Process an ETL manifest.

        Processing behavior:

        1. Group files by dataset/month.
        2. Separate fixed TO coordinate masters.
        3. Determine business months only from month-aware groups.
        4. Merge monthly CUSTOMER_LOCATION data together with the
           fixed coordinate masters.
        5. Never create a monthless CUSTOMER_LOCATION parquet.
        6. Never infer a month from the TO files.
        """

        files = manifest.get("files") or []

        if not files:
            raise ValueError(
                "Manifest does not contain uploaded files."
            )

        grouped = FileGrouper.group(
            files,
        )

        if not grouped:
            raise ValueError(
                "No files available for ETL processing."
            )

        job_folder = manifest.get(
            "job_folder",
        )

        if not job_folder:
            raise ValueError(
                "Manifest does not contain 'job_folder'."
            )

        outputs: list[str] = []

        # ======================================================
        # FIND FIXED COORDINATE MASTERS
        # ======================================================

        coordinate_master_files: list[Path] = []

        for (
            dataset,
            month,
        ), grouped_files in grouped.items():

            if dataset != FileDetector.CUSTOMER_LOCATION:
                continue

            for file in cls._valid_files(
                grouped_files,
            ):
                filename = file.get("filename")

                if not filename:
                    continue

                if cls._is_coordinate_master_file(
                    filename,
                ):
                    coordinate_master_files.append(
                        Path(job_folder) / filename
                    )

        # Remove duplicates while preserving order.
        coordinate_master_files = list(
            dict.fromkeys(
                coordinate_master_files,
            )
        )

        logger.info(
            "Coordinate master files: %s",
            [
                path.name
                for path in coordinate_master_files
            ],
        )

        # ======================================================
        # DETERMINE BUSINESS MONTHS
        # ======================================================

        business_months = sorted(
            {
                month
                for (
                    _dataset,
                    month,
                ) in grouped.keys()
                if month is not None
            }
        )

        logger.info(
            "Business months detected: %s",
            business_months,
        )

        # ======================================================
        # PROCESS GROUPS
        # ======================================================

        processed_customer_location_months: set[str] = set()

        for (
            dataset,
            month,
        ), grouped_files in grouped.items():

            valid_files = cls._valid_files(
                grouped_files,
            )

            if not valid_files:
                logger.warning(
                    "Skipping invalid group: dataset=%s month=%s",
                    dataset,
                    month,
                )
                continue

            # --------------------------------------------------
            # Monthless CUSTOMER_LOCATION
            # --------------------------------------------------
            #
            # This is the fixed TO master group.
            #
            # Never call MonthlyMerger here.
            # --------------------------------------------------

            if (
                dataset == FileDetector.CUSTOMER_LOCATION
                and month is None
            ):
                logger.info(
                    "Skipping monthless CUSTOMER_LOCATION group; "
                    "files are fixed coordinate masters."
                )
                continue

            # --------------------------------------------------
            # Monthly CUSTOMER_LOCATION
            # --------------------------------------------------

            if dataset == FileDetector.CUSTOMER_LOCATION:

                if month is None:
                    continue

                monthly_paths = cls._manifest_paths(
                    job_folder,
                    valid_files,
                )

                if not monthly_paths:
                    continue

                # Fixed TO masters are authoritative coordinate
                # sources and are placed before monthly DIL files.
                combined_paths = list(
                    dict.fromkeys(
                        coordinate_master_files
                        + monthly_paths
                    )
                )

                logger.info(
                    "Processing CUSTOMER_LOCATION month=%s; "
                    "coordinate_masters=%s, monthly_files=%s",
                    month,
                    len(coordinate_master_files),
                    len(monthly_paths),
                )

                output = MonthlyMerger.merge(
                    dataset=dataset,
                    month=month,
                    files=combined_paths,
                    output_dir=cls.OUTPUT,
                )

                outputs.append(
                    str(output),
                )

                processed_customer_location_months.add(
                    str(month),
                )

                continue

            # --------------------------------------------------
            # Other monthly datasets
            # --------------------------------------------------

            paths = cls._manifest_paths(
                job_folder,
                valid_files,
            )

            if not paths:
                continue

            # A non-CUSTOMER_LOCATION dataset must have a business
            # month. This prevents accidental monthless exports.
            if month is None:
                logger.warning(
                    "Skipping monthless dataset=%s because it is not "
                    "a coordinate master.",
                    dataset,
                )
                continue

            output = MonthlyMerger.merge(
                dataset=dataset,
                month=month,
                files=paths,
                output_dir=cls.OUTPUT,
            )

            outputs.append(
                str(output),
            )

        # ======================================================
        # MONTHS WITH TO MASTER BUT WITHOUT DIL
        # ======================================================
        #
        # If a business month exists elsewhere in the upload but
        # there is no DIL/CUSTOMER_LOCATION file for that month,
        # create customer_location_<month>.parquet from the fixed
        # coordinate masters alone.
        #
        # This is deliberately done only when:
        #
        #   - coordinate masters exist
        #   - a business month exists
        #
        # The TO files themselves still never receive a month.
        # ======================================================

        if coordinate_master_files:

            for month in business_months:

                month_key = str(month)

                if month_key in (
                    processed_customer_location_months
                ):
                    continue

                logger.info(
                    "Creating CUSTOMER_LOCATION month=%s "
                    "from fixed coordinate masters only.",
                    month,
                )

                output = MonthlyMerger.merge(
                    dataset=FileDetector.CUSTOMER_LOCATION,
                    month=month,
                    files=coordinate_master_files,
                    output_dir=cls.OUTPUT,
                )

                outputs.append(
                    str(output),
                )

        logger.info(
            "ETL processing completed. Outputs=%s",
            len(outputs),
        )

        return outputs