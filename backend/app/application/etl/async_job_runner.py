from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.application.etl.etl_orchestrator import ETLOrchestrator

logger = logging.getLogger(__name__)

_tasks: dict[str, asyncio.Task[Any]] = {}


def _cleanup(job_id: str) -> None:
    _tasks.pop(job_id, None)


async def run_etl_background(job_id: str, job_folder: Path) -> None:
    """Run ETL outside the HTTP request lifecycle.

    The HTTP endpoint must never wait on a long ETL operation. This prevents
    Cloudflare/proxy timeouts and also keeps the process endpoint responsive.
    """
    try:
        result = await asyncio.to_thread(ETLOrchestrator.process, job_folder)
        if not isinstance(result, dict) or result.get("success") is not True:
            logger.error("Background ETL failed | job=%s | result=%r", job_id, result)
        else:
            logger.info("Background ETL completed | job=%s", job_id)
    except asyncio.CancelledError:
        logger.warning("Background ETL task cancelled | job=%s", job_id)
        raise
    except Exception:
        logger.exception("Background ETL crashed | job=%s", job_id)
    finally:
        _cleanup(job_id)


def start_etl_background(job_id: str, job_folder: Path) -> bool:
    """Start at most one in-process ETL task per job."""
    existing = _tasks.get(job_id)
    if existing and not existing.done():
        return False

    task = asyncio.create_task(run_etl_background(job_id, job_folder))
    _tasks[job_id] = task
    return True


def is_etl_running(job_id: str) -> bool:
    task = _tasks.get(job_id)
    return bool(task and not task.done())
