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


async def recover_one_pending_job() -> dict[str, Any]:
    """Recover at most one eligible unfinished durable ETL job.

    Startup must never fan out into every historical job: the production
    instance has a tight memory budget. One-job recovery is deliberately
    serialized and non-blocking for FastAPI startup.

    Failed jobs that already exhausted the retry budget are ignored here.
    They must not permanently block newer recoverable jobs at the head of the
    queue on every deployment restart.
    """
    async with _RECOVERY_LOCK:
        jobs = await asyncio.to_thread(_load_pending_jobs)

        eligible_jobs = []
        exhausted_jobs = 0
        for metadata in jobs:
            status = str(metadata.get("status") or "").upper()
            attempts = int(metadata.get("recovery_attempts") or 0)
            if (
                status == "FAILED"
                and attempts >= MAX_FAILED_RECOVERY_ATTEMPTS
            ):
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

        metadata = eligible_jobs[0]
        job_id = str(metadata.get("job_id") or "").strip()
        logger.warning(
            "STARTUP RECOVERY: processing one eligible pending job | job=%s | eligible=%s | exhausted=%s",
            job_id,
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
