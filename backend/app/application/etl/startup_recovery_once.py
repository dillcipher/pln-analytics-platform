from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.etl.startup_recovery_safe import (
    MAX_FAILED_RECOVERY_ATTEMPTS,
    RECOVERY_POLICY_VERSION,
    _LOCK,
    _load_jobs,
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


def _is_eligible(metadata: dict[str, Any]) -> bool:
    attempts = int(metadata.get("recovery_attempts") or 0)
    policy = str(metadata.get("recovery_policy_version") or "")
    if attempts < MAX_FAILED_RECOVERY_ATTEMPTS:
        return True
    if policy != RECOVERY_POLICY_VERSION:
        logger.warning(
            "STARTUP RECOVERY: old exhausted job is eligible after policy change | job=%s | attempts=%s | old_policy=%s | new_policy=%s",
            metadata.get("job_id"), attempts, policy or "<none>", RECOVERY_POLICY_VERSION,
        )
        return True
    return False


async def recover_one_pending_job() -> dict[str, Any]:
    """Recover at most one durable job; terminal detector failures are rejected."""
    async with _LOCK:
        jobs = await asyncio.to_thread(_load_jobs)
        eligible = [job for job in jobs if _is_eligible(job)]
        exhausted = len(jobs) - len(eligible)
        if not eligible:
            logger.info("STARTUP RECOVERY: no eligible unfinished durable jobs found | exhausted=%s", exhausted)
            return {"found": len(jobs), "eligible": 0, "recovered": 0, "failed": 0, "rejected": 0, "exhausted": exhausted}

        metadata = min(
            eligible,
            key=lambda item: (
                _file_size(item) if _file_size(item) > 0 else 2**63,
                str(item.get("uploaded_at") or item.get("created_at") or ""),
            ),
        )
        job_id = str(metadata.get("job_id") or "").strip()
        logger.warning(
            "STARTUP RECOVERY: processing one eligible pending job | job=%s | size=%s | eligible=%s | exhausted=%s",
            job_id, _file_size(metadata), len(eligible), exhausted,
        )
        result = await _recover_one(metadata)
        return {
            "found": len(jobs),
            "eligible": len(eligible),
            "recovered": 1 if result == "recovered" else 0,
            "failed": 1 if result == "failed" else 0,
            "rejected": 1 if result == "rejected" else 0,
            "exhausted": exhausted,
        }
