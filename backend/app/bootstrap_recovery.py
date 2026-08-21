from __future__ import annotations

"""Production bootstrap fixes for DLPD month resolution and durable recovery."""

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

        try:
            dataset = FileDetector.detect(filepath)
            sheet = DatasetValidator.get_sheet_name(filepath, dataset)
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
                    filepath, sorted(resolved),
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

    transient = {"FAILED", "UPLOADED", "MERGING", "EXPORTING", "ASSEMBLY_QUEUED"}

    async def _resume_job(job_id: str) -> None:
        """Resume assembly/ETL for a durable job without another upload."""
        try:
            job_folder = job_recovery.RAW_UPLOAD / job_id
            metadata_key = job_recovery.UploadService._job_metadata_s3_key(job_id)
            if not await job_recovery.UploadService._s3_head(metadata_key):
                logger.warning("RECOVERY JOB METADATA NOT FOUND | JOB=%s", job_id)
                return

            metadata = await job_recovery.UploadService._s3_get_json(metadata_key)
            status = str((metadata or {}).get("status", "")).upper()
            if status not in transient:
                logger.info("STARTUP RECOVERY SKIP | JOB=%s | STATUS=%s", job_id, status or "UNKNOWN")
                return

            logger.warning("STARTUP RECOVERY RUN | JOB=%s | STATUS=%s | NO REUPLOAD", job_id, status)

            manifest = await job_recovery._restore_manifest(job_id, job_folder)

            # Assembly was interrupted before manifest creation. Continue
            # directly from the already stored Supabase chunks.
            if manifest is None:
                upload_id = str((metadata or {}).get("upload_id") or "").strip()
                filename = str(
                    (metadata or {}).get("filename")
                    or (metadata or {}).get("original_filename")
                    or ""
                ).strip()
                total_chunks = int((metadata or {}).get("total_chunks") or 0)

                if not upload_id or not filename or total_chunks <= 0:
                    logger.error("ASSEMBLY RECOVERY MISSING METADATA | JOB=%s", job_id)
                    return

                logger.warning(
                    "ASSEMBLY RECOVERY FROM SUPABASE CHUNKS | JOB=%s | FILE=%s | CHUNKS=%s | NO REUPLOAD",
                    job_id, filename, total_chunks,
                )
                await job_recovery.UploadService.assemble_chunk_upload(
                    upload_id=upload_id,
                    job_id=job_id,
                    filename=filename,
                    total_chunks=total_chunks,
                    content_type=(metadata or {}).get("content_type"),
                )
                manifest = await job_recovery._restore_manifest(job_id, job_folder)
                if manifest is None:
                    logger.error("RECOVERY MANIFEST STILL MISSING AFTER ASSEMBLY | JOB=%s", job_id)
                    return

            # Restore the assembled workbook from durable storage. Legacy
            # jobs without a durable final file are reassembled from chunks.
            if not await job_recovery._restore_manifest_files(job_id, job_folder, manifest):
                upload_id = str((metadata or {}).get("upload_id") or "").strip()
                filename = str(
                    (metadata or {}).get("filename")
                    or (metadata or {}).get("original_filename")
                    or ""
                ).strip()
                total_chunks = int((metadata or {}).get("total_chunks") or 0)

                if not upload_id or not filename or total_chunks <= 0:
                    logger.error("LEGACY RECOVERY MISSING CHUNK METADATA | JOB=%s", job_id)
                    return

                logger.warning("LEGACY FILE RECOVERY FROM SUPABASE CHUNKS | JOB=%s | NO REUPLOAD", job_id)
                await job_recovery.UploadService.assemble_chunk_upload(
                    upload_id=upload_id,
                    job_id=job_id,
                    filename=filename,
                    total_chunks=total_chunks,
                    content_type=(metadata or {}).get("content_type"),
                )

                if not await job_recovery._restore_manifest_files(job_id, job_folder, manifest):
                    logger.error("STARTUP RECOVERY BLOCKED | JOB=%s | REQUIRED ASSEMBLED FILE MISSING", job_id)
                    return

            await job_recovery._run_etl_with_retry(job_id, job_folder)
        except Exception:
            logger.exception("Durable transient job recovery failed for %s", job_id)
        finally:
            job_recovery._RUNNING_JOB_IDS.discard(job_id)

    def ensure_job_processing(job_id: str) -> None:
        job_id = job_id.strip()
        if not job_id or job_id in job_recovery._RUNNING_JOB_IDS:
            return
        job_recovery._RUNNING_JOB_IDS.add(job_id)
        task = asyncio.create_task(_resume_job(job_id))

        def _done(completed: asyncio.Task) -> None:
            try:
                completed.exception()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Unexpected recovery task failure for %s", job_id)

        task.add_done_callback(_done)

    async def recover_transient_jobs() -> None:
        try:
            client = job_recovery._create_s3_client()
            response = await asyncio.to_thread(
                client.list_objects_v2,
                Bucket=job_recovery.S3_BUCKET,
                Prefix="jobs/",
            )
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
                            job_id, status,
                        )
                        ensure_job_processing(job_id)
                        recovered += 1
                except Exception:
                    logger.exception("Could not inspect transient durable job %s", job_id)
            logger.info("STARTUP TRANSIENT JOB RECOVERY COMPLETED | RECOVERED=%s", recovered)
        except Exception:
            logger.exception("Startup transient job recovery extension failed")

    # Override both entry points. The existing job_recovery implementation
    # only resumed FAILED manifests, which is exactly why MERGING/UPLOADED
    # jobs were logged as recovered but then immediately skipped.
    job_recovery.ensure_job_processing = ensure_job_processing
    job_recovery.recover_failed_jobs_on_startup = recover_transient_jobs
    job_recovery._pln_recovery_extension_installed = True


_install_month_resolution_fallback()
_install_startup_recovery_extension()
