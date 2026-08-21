from __future__ import annotations

"""Small production bootstrap fixes for durable ETL recovery.

This module is imported from ``app.__init__`` so it runs before
``app.main`` imports the application modules. It keeps the compatibility
fixes isolated instead of spreading special cases through the ETL code.
"""

import asyncio
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _install_month_resolution_fallback() -> None:
    try:
        from app.etl.detector.detector import FileDetector
        from app.etl.detector.month_resolver import MonthResolver
        from app.etl.validator.validator import DatasetValidator
    except Exception:
        logger.exception("Could not initialize DLPD month fallback")
        return

    if getattr(MonthResolver, "_pln_fallback_installed", False):
        return

    original = MonthResolver.resolve_months.__func__

    @classmethod
    def resolve_months_with_fallback(cls, filepath):
        months = original(cls, filepath)
        if months or FileDetector.detect(filepath) not in {
            FileDetector.DLPD_PASCABAYAR,
            FileDetector.DLPD_PRABAYAR,
        }:
            return months

        # Some historical DLPD workbooks use a header layout that the
        # lightweight resolver cannot recognize. Read only month/date
        # columns as a compatibility fallback; the full workbook is still
        # processed normally later by MonthlyMerger.
        try:
            sheet = DatasetValidator.get_sheet_name(filepath, FileDetector.detect(filepath))
            header = DatasetValidator.detect_header_row(filepath=filepath, sheet_name=sheet)
            header_frame = pd.read_excel(filepath, sheet_name=sheet, header=header, nrows=0)
            normalized = {
                DatasetValidator.normalize_column(column): column
                for column in header_frame.columns
            }

            wanted = []
            for normalized_name, original_name in normalized.items():
                if normalized_name in {
                    DatasetValidator.normalize_column("THBL"),
                    DatasetValidator.normalize_column("THBLREK"),
                    DatasetValidator.normalize_column("DLPD_TGLBACA"),
                    DatasetValidator.normalize_column("MONTH"),
                } or any(token in normalized_name for token in ("THBL", "THBLREK", "DLPD_TGLBACA")):
                    wanted.append(original_name)

            if not wanted:
                logger.warning("DLPD month fallback found no month/date columns | FILE=%s", filepath)
                return months

            frame = pd.read_excel(filepath, sheet_name=sheet, header=header, usecols=wanted)
            resolved: set[str] = set()
            for column in frame.columns:
                normalized_column = DatasetValidator.normalize_column(column)
                for value in frame[column]:
                    month = cls._normalize_month(value)
                    if month:
                        resolved.add(month)

                if normalized_column == DatasetValidator.normalize_column("DLPD_TGLBACA"):
                    for value in frame[column]:
                        parsed = cls._parse_date(value)
                        if parsed is not None:
                            resolved.add(parsed.strftime("%Y%m"))

            if resolved:
                logger.warning(
                    "DLPD MONTH FALLBACK RESOLVED | FILE=%s | MONTHS=%s",
                    filepath,
                    sorted(resolved),
                )
                return sorted(resolved)
        except Exception:
            logger.exception("DLPD month fallback failed | FILE=%s", filepath)

        return months

    MonthResolver.resolve_months = resolve_months_with_fallback
    MonthResolver._pln_fallback_installed = True
    logger.info("DLPD month-resolution compatibility fallback installed")


def _install_startup_recovery_extension() -> None:
    try:
        from app.application.jobs import job_recovery
    except Exception:
        logger.exception("Could not initialize startup recovery extension")
        return

    if getattr(job_recovery, "_pln_recovery_extension_installed", False):
        return

    original = job_recovery.recover_failed_jobs_on_startup

    async def recover_transient_jobs() -> None:
        await original()

        try:
            client = job_recovery._create_s3_client()
            response = await asyncio.to_thread(
                client.list_objects_v2,
                Bucket=job_recovery.S3_BUCKET,
                Prefix="jobs/",
            )

            transient = {"UPLOADED", "MERGING", "EXPORTING", "ASSEMBLY_QUEUED"}
            recovered = 0

            for item in response.get("Contents", []):
                key = str(item.get("Key", ""))
                if not key.endswith("/job.json"):
                    continue
                job_id = key[len("jobs/"):-len("/job.json")]
                if not job_id:
                    continue

                try:
                    data = await job_recovery.UploadService._s3_get_json(key)
                    status = str((data or {}).get("status", "")).upper()
                    if status in transient:
                        logger.warning(
                            "STARTUP TRANSIENT JOB RECOVERY | JOB=%s | STATUS=%s | NO REUPLOAD",
                            job_id,
                            status,
                        )
                        job_recovery.ensure_job_processing(job_id)
                        recovered += 1
                except Exception:
                    logger.exception("Could not inspect transient durable job %s", job_id)

            logger.info("STARTUP TRANSIENT JOB RECOVERY COMPLETED | RECOVERED=%s", recovered)
        except Exception:
            logger.exception("Startup transient job recovery extension failed")

    job_recovery.recover_failed_jobs_on_startup = recover_transient_jobs
    job_recovery._pln_recovery_extension_installed = True


_install_month_resolution_fallback()
_install_startup_recovery_extension()
