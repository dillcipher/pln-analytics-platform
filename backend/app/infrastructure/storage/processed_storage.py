from __future__ import annotations

import logging
import os
from pathlib import Path

import boto3
from botocore.client import Config

from app.core.constants import PROCESSED, WAREHOUSE

logger = logging.getLogger(__name__)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "").strip()
S3_REGION = os.getenv("S3_REGION", "ap-southeast-1").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
S3_BUCKET = os.getenv("S3_BUCKET", "pln-analytics-uploads").strip()
S3_PREFIX = os.getenv("S3_PROCESSED_PREFIX", "processed").strip().strip("/")


def _client():
    if not S3_ENDPOINT or not S3_ACCESS_KEY_ID or not S3_SECRET_ACCESS_KEY:
        return None
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=600,
            s3={"addressing_style": "path"},
        ),
    )


def _key(path: Path) -> str:
    return f"{S3_PREFIX}/{path.relative_to(PROCESSED).as_posix()}"


def _download_object(client, bucket: str, key: str, destination: Path) -> None:
    """Stream an object through GetObject instead of relying on HEAD metadata."""
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    temporary = destination.with_suffix(destination.suffix + ".download")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("wb") as fh:
            while True:
                chunk = body.read(8 * 1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(temporary, destination)
    finally:
        body.close()
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _upload_object(client, bucket: str, key: str, source: Path, content_type: str) -> None:
    """Use one streaming PutObject so Supabase UploadPart is never involved."""
    size = source.stat().st_size
    with source.open("rb") as fh:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=fh,
            ContentLength=size,
            ContentType=content_type,
        )


def hydrate_processed_data() -> int:
    """Restore durable processed data into the local cloud-instance cache."""
    client = _client()
    if client is None:
        logger.warning("Processed storage is not configured; using local data only.")
        return 0

    PROCESSED.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/"):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if not key or key.endswith("/"):
                    continue

                relative = key[len(f"{S3_PREFIX}/"):]
                destination = PROCESSED / relative
                _download_object(client, S3_BUCKET, key, destination)
                downloaded += 1
                logger.info("Hydrated processed artifact: %s", relative)
    except Exception:
        logger.exception("Failed to hydrate processed data from object storage.")

    logger.info("Processed data hydration completed: %s file(s).", downloaded)
    return downloaded


def persist_processed_data() -> int:
    """Persist parquet, warehouse, and metadata using durable streaming PUTs."""
    client = _client()
    if client is None:
        logger.warning("Processed storage is not configured; processed data remains local.")
        return 0

    uploaded = 0
    try:
        candidates = [path for path in PROCESSED.rglob("*") if path.is_file()]
        if WAREHOUSE.exists() and WAREHOUSE not in candidates:
            candidates.append(WAREHOUSE)

        for path in candidates:
            content_type = "application/octet-stream"
            if path.suffix.lower() == ".parquet":
                content_type = "application/vnd.apache.parquet"
            elif path.suffix.lower() == ".json":
                content_type = "application/json"
            elif path.suffix.lower() == ".duckdb":
                content_type = "application/vnd.duckdb"

            _upload_object(
                client,
                S3_BUCKET,
                _key(path),
                path,
                content_type,
            )
            uploaded += 1

    except Exception:
        logger.exception("Failed to persist processed data to object storage.")
        raise

    logger.info("Processed data persistence completed: %s file(s).", uploaded)
    return uploaded
