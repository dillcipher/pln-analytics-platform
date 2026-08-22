from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.etl.startup_recovery import (
    _RECOVERY_LOCK,
    _load_pending_jobs,
    _recover_one,
)

logger = logging.getLogger(__name__)


async def recover_one_pending_job() -> dict[str, Any]:
    """Recover at most one unfinished durable ETL job.

    Startup must never fan out into every historical job: the production
    instance has a tight memory budget. One-job recovery is deliberately
    serialized and non-blocking for FastAPI startup. If more work remains,
    the next deployment/startup can pick up the next job after the first one
    has been marked FINISHED.
    """
    async with _RECOVERY_LOCK:
        jobs = await asyncio.to_thread(_load_pending_jobs)
        if not jobs:
            logger.info("STARTUP RECOVERY: no unfinished durable jobs found")
            return {"found": 0, "recovered": 0, "failed": 0}

        metadata = jobs[0]
        job_id = str(metadata.get("job_id") or "").strip()
        logger.warning(
            "STARTUP RECOVERY: processing one pending job | job=%s | remaining=%s",
            job_id,
            len(jobs),
        )

        recovered = await _recover_one(metadata)
        return {
            "found": len(jobs),
            "recovered": 1 if recovered else 0,
            "failed": 0 if recovered else 1,
        }
