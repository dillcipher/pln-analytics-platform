from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path

import boto3
from botocore.client import Config

from app.core.constants import RAW_UPLOAD

logger = logging.getLogger(__name__)

_ETL_LOCK = threading.Lock()
_INSTALLED = False
S3_UPLOAD_RETRIES = max(1, int(os.getenv("S3_UPLOAD_RETRIES", "3")))


def _s3_configured() -> bool:
    return all(
        os.getenv(name, "").strip()
        for name in (
            "S3_ENDPOINT",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
        )
    )


def install_runtime_guards() -> None:
    """Install the production execution contract before API routes load."""
    global _INSTALLED
    if _INSTALLED:
        return

    from app.application.etl.etl_orchestrator import ETLOrchestrator
    from app.services.upload_service import UploadService, S3_BUCKET

    UploadService.UPLOAD_FOLDER = RAW_UPLOAD

    # ----------------------------------------------------------
    # Stable S3 single-PUT upload
    # ----------------------------------------------------------
    if not getattr(UploadService, "_pln_stable_s3_upload", False):
        async def _stable_s3_put_file(cls, local_path: Path, s3_key: str) -> None:
            if not _s3_configured():
                raise RuntimeError(
                    "Durable storage is not configured: S3_ENDPOINT, "
                    "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required."
                )

            size = local_path.stat().st_size
            if size > 5 * 1024 * 1024 * 1024:
                raise ValueError(
                    f"File {local_path.name} exceeds the 5 GiB single-object upload limit."
                )

            def _upload() -> None:
                last_error: Exception | None = None
                for attempt in range(1, S3_UPLOAD_RETRIES + 1):
                    try:
                        client = boto3.client(
                            "s3",
                            endpoint_url=os.getenv("S3_ENDPOINT", "").strip(),
                            region_name=os.getenv("S3_REGION", "ap-southeast-1").strip(),
                            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", "").strip(),
                            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", "").strip(),
                            config=Config(
                                signature_version="s3v4",
                                retries={"max_attempts": 5, "mode": "adaptive"},
                                connect_timeout=30,
                                read_timeout=600,
                                s3={"addressing_style": "path"},
                            ),
                        )
                        with local_path.open("rb") as source:
                            client.put_object(
                                Bucket=S3_BUCKET,
                                Key=s3_key,
                                Body=source,
                                ContentLength=size,
                                ContentType="application/octet-stream",
                            )
                        logger.info(
                            "STABLE S3 SINGLE-PUT OK | FILE=%s | BYTES=%s | ATTEMPT=%s",
                            local_path.name,
                            size,
                            attempt,
                        )
                        return
                    except Exception as exc:
                        last_error = exc
                        logger.warning(
                            "STABLE S3 UPLOAD RETRY | FILE=%s | ATTEMPT=%s/%s | ERROR=%r",
                            local_path.name,
                            attempt,
                            S3_UPLOAD_RETRIES,
                            exc,
                        )
                        if attempt < S3_UPLOAD_RETRIES:
                            time.sleep(min(2 * attempt, 8))
                raise last_error if last_error is not None else RuntimeError("S3 upload failed")

            await asyncio.to_thread(_upload)

        UploadService._s3_put_file = classmethod(_stable_s3_put_file)
        UploadService._pln_stable_s3_upload = True

    # ----------------------------------------------------------
    # Stable S3 streaming download
    # ----------------------------------------------------------
    if not getattr(UploadService, "_pln_stable_s3_download", False):
        async def _stable_s3_download_file(cls, s3_key: str, local_path: Path) -> None:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            if not _s3_configured():
                raise RuntimeError("Durable storage is not configured.")

            def _download() -> None:
                client = boto3.client(
                    "s3",
                    endpoint_url=os.getenv("S3_ENDPOINT", "").strip(),
                    region_name=os.getenv("S3_REGION", "ap-southeast-1").strip(),
                    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", "").strip(),
                    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", "").strip(),
                    config=Config(
                        signature_version="s3v4",
                        retries={"max_attempts": 5, "mode": "adaptive"},
                        connect_timeout=30,
                        read_timeout=600,
                        s3={"addressing_style": "path"},
                    ),
                )
                response = client.get_object(Bucket=S3_BUCKET, Key=s3_key)
                body = response["Body"]
                temporary = local_path.with_suffix(local_path.suffix + ".download")
                try:
                    with temporary.open("wb") as target:
                        while True:
                            chunk = body.read(8 * 1024 * 1024)
                            if not chunk:
                                break
                            target.write(chunk)
                    os.replace(temporary, local_path)
                finally:
                    body.close()
                    if temporary.exists():
                        temporary.unlink(missing_ok=True)

            await asyncio.to_thread(_download)

        UploadService._s3_download_file = classmethod(_stable_s3_download_file)
        UploadService._pln_stable_s3_download = True

    # ----------------------------------------------------------
    # Small-file durability
    # ----------------------------------------------------------
    if not getattr(UploadService, "_pln_durable_small_upload", False):
        original_save_files = UploadService.save_files.__func__

        async def _durable_save_files(cls, files):
            result = await original_save_files(cls, files)
            if not _s3_configured():
                return result

            job_id = str(result.get("job_id") or "").strip()
            if not job_id:
                raise RuntimeError("Upload succeeded without a job_id.")

            job_folder = RAW_UPLOAD / job_id
            for record in result.get("files") or []:
                filename = str(record.get("filename") or "").strip()
                if not filename:
                    continue
                local_file = job_folder / filename
                if not local_file.exists():
                    raise FileNotFoundError(
                        f"Uploaded file disappeared before durable persistence: {local_file}"
                    )
                await cls._s3_put_file(
                    local_file,
                    cls._job_file_s3_key(job_id, filename),
                )

            manifest = job_folder / "manifest.json"
            if manifest.exists():
                await cls._s3_put_json(
                    cls._job_manifest_s3_key(job_id),
                    json.loads(manifest.read_text(encoding="utf-8")),
                )

            logger.info(
                "SMALL UPLOAD DURABLE | JOB=%s | FILES=%s",
                job_id,
                len(result.get("files") or []),
            )
            return result

        UploadService.save_files = classmethod(_durable_save_files)
        UploadService._pln_durable_small_upload = True

    # ----------------------------------------------------------
    # DLPD query hardening
    # ----------------------------------------------------------
    # The repository already owns month semantics; this guard only adds the
    # tariff predicate that the domain filter object exposes but the legacy SQL
    # builder omitted. It keeps all DLPD surfaces (KPI/ULP/list/map/export)
    # consistent without duplicating the repository implementation.
    from app.infrastructure.duckdb.dlpd_repository import DuckDbDlpdRepository

    if not getattr(DuckDbDlpdRepository, "_pln_filter_hardened", False):
        original_build_where = DuckDbDlpdRepository._build_where

        def _hardened_build_where(self, customer_type, month_key, filters):
            sql, params = original_build_where(
                self,
                customer_type,
                month_key,
                filters,
            )
            tariff = str(getattr(filters, "tariff", "") or "").strip()
            if tariff:
                clause = "TRIM(CAST(d.TARIF AS VARCHAR)) = ?"
                if sql:
                    sql = f"{sql}\nAND ({clause})"
                else:
                    sql = f"WHERE ({clause})"
                params.append(tariff)
            return sql, params

        DuckDbDlpdRepository._build_where = _hardened_build_where
        DuckDbDlpdRepository._pln_filter_hardened = True

    # ----------------------------------------------------------
    # Serialized ETL
    # ----------------------------------------------------------
    if not getattr(ETLOrchestrator, "_pln_serialized", False):
        original_process = ETLOrchestrator.process.__func__

        def _serialized_process(cls, job_folder: Path):
            logger.info("ETL MEMORY GATE WAIT | JOB=%s", job_folder.name)
            with _ETL_LOCK:
                logger.info("ETL MEMORY GATE ACQUIRED | JOB=%s", job_folder.name)
                try:
                    return original_process(cls, job_folder)
                finally:
                    logger.info("ETL MEMORY GATE RELEASED | JOB=%s", job_folder.name)

        ETLOrchestrator.process = classmethod(_serialized_process)
        ETLOrchestrator._pln_serialized = True

    _INSTALLED = True
    logger.info(
        "Production runtime guards installed: durable uploads + streaming S3 + serialized ETL"
    )
