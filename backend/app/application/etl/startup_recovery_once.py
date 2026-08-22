from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.etl.startup_recovery import (
    MAX_FAILED_RECOVERY_ATTEMPTS,
    _RECOVERY_LOCK,
    _load_pending_jobs,
    _recover_one,
)

logger = logging.getLogger(__name__)


def _file_size(metadata: dict[str, Any]) -> int:
    files = metadata.get("files")
    if isinstance(files, list) and files and isinstance(files[0], dict):
        try:
            return int(files[0].get("size") or 0)
        except (TypeError, ValueError):
            pass
    try:
        return int(metadata.get("size") or 0)
    except (TypeError, ValueError):
        return 0


async def recover_one_pending_job() -> dict[str, Any]:
    """Recover at most one unfinished durable ETL job safely."""
    async with _RECOVERY_LOCK:
        jobs = await asyncio.to_thread(_load_pending_jobs)

        eligible_jobs = []
        exhausted_jobs = 0
        for metadata in jobs:
            attempts = int(metadata.get("recovery_attempts") or 0)
            # Retry budget applies to every recoverable state. A job must not
            # escape the limit merely because its last state remained MERGING
            # or TRANSFORMING after a container restart.
            if attempts >= MAX_FAILED_RECOVERY_ATTEMPTS:
                exhausted_jobs += 1
                continue
            eligible_jobs.append(metadata)

        if not eligible_jobs:
            logger.info(
                "STARTUP RECOVERY: no eligible unfinished durable jobs found | exhausted=%s",
                exhausted_jobs,
            )
            return {
                "found": len(jobs),
                "eligible": 0,
                "recovered": 0,
                "failed": 0,
                "exhausted": exhausted_jobs,
            }

        # Smallest-first is deliberate. A pending 40 MB DLPD workbook is a
        # much safer startup recovery candidate than a 745+ MB workbook.
        metadata = min(
            eligible_jobs,
            key=lambda item: (
                _file_size(item) if _file_size(item) > 0 else 2**63,
                str(item.get("uploaded_at") or item.get("created_at") or ""),
            ),
        )

        job_id = str(metadata.get("job_id") or "").strip()
        logger.warning(
            "STARTUP RECOVERY: processing one eligible pending job | job=%s | size=%s | eligible=%s | exhausted=%s",
            job_id,
            _file_size(metadata),
            len(eligible_jobs),
            exhausted_jobs,
        )

        recovered = await _recover_one(metadata)
        return {
            "found": len(jobs),
            "eligible": len(eligible_jobs),
            "recovered": 1 if recovered else 0,
            "failed": 0 if recovered else 1,
            "exhausted": exhausted_jobs,
        }
