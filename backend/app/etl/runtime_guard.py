from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path

import boto3
from botocore.client import Config
from boto3.s3.transfer import TransferConfig

logger = logging.getLogger(__name__)

_ETL_LOCK = threading.Lock()
_INSTALLED = False


def install_runtime_guards() -> None:
    """Install production guards before any upload/ETL work starts.

    Large Excel processing is memory-heavy. The application must never run
    multiple ETL pipelines concurrently, and boto3 must not use its default
    multi-threaded multipart uploader on a small cloud instance.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from app.application.etl.etl_orchestrator import ETLOrchestrator
    from app.services.upload_service import UploadService, S3_BUCKET

    if not getattr(UploadService, "_pln_stable_s3_upload", False):
        async def _stable_s3_put_file(
            cls,
            local_path: Path,
            s3_key: str,
        ) -> None:
            size = local_path.stat().st_size
            transfer = TransferConfig(
                multipart_threshold=64 * 1024 * 1024,
                multipart_chunksize=16 * 1024 * 1024,
                max_concurrency=1,
                use_threads=False,
            )

            def _upload() -> None:
                client = boto3.client(
                    "s3",
                    endpoint_url=os.getenv("S3_ENDPOINT", "").strip(),
                    region_name=os.getenv("S3_REGION", "ap-southeast-1").strip(),
                    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", "").strip(),
                    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", "").strip(),
                    config=Config(
                        signature_version="s3v4",
                        retries={"max_attempts": 5, "mode": "adaptive"},
                        connect_timeout=20,
                        read_timeout=180,
                    ),
                )
                client.upload_file(
                    str(local_path),
                    S3_BUCKET,
                    s3_key,
                    ExtraArgs={"ContentType": "application/octet-stream"},
                    Config=transfer,
                )

            await asyncio.to_thread(_upload)
            logger.info("STABLE S3 UPLOAD OK | FILE=%s | BYTES=%s", local_path.name, size)

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
