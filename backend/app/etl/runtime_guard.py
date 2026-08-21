from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from pathlib import Path

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)

_ETL_LOCK = threading.Lock()
_INSTALLED = False
S3_UPLOAD_RETRIES = max(1, int(os.getenv("S3_UPLOAD_RETRIES", "3")))


def install_runtime_guards() -> None:
    """Install production guards before any upload/ETL work starts."""
    global _INSTALLED
    if _INSTALLED:
        return

    from app.application.etl.etl_orchestrator import ETLOrchestrator
    from app.services.upload_service import UploadService, S3_BUCKET

    if not getattr(UploadService, "_pln_stable_s3_upload", False):
        async def _stable_s3_put_file(cls, local_path: Path, s3_key: str) -> None:
            size = local_path.stat().st_size
            # Supabase Storage's S3 gateway has been returning opaque
            # UploadPart failures for multipart uploads. PLN workbooks are
            # uploaded as a streaming single PUT instead. This is constant
            # memory and avoids the multipart UploadPart path entirely.
            single_put_limit = 5 * 1024 * 1024 * 1024
            if size > single_put_limit:
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
                            ),
                        )
                        with local_path.open("rb") as source:
                            client.put_object(
                                Bucket=S3_BUCKET,
                                Key=s3_key,
                                Body=source,
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
    logger.info("Production runtime guards installed: serialized ETL + stable S3 transfers")
