"""Make chunk completion durable instead of starting heavy work in-request.

The upload endpoint historically scheduled assembly + ETL immediately after
``/upload/complete``. That creates a second execution path beside durable
startup recovery and can race with recovery after a restart. The durable
worker is now the single owner of chunk assembly/ETL.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_INSTALLED = False


def install_durable_upload_queue_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.interface.api.v1 import upload as upload_module

    async def _durable_worker_noop(
        upload_id: str,
        job_id: str,
        filename: str,
        total_chunks: int,
        content_type: str | None,
    ) -> None:
        """Intentionally empty: durable worker owns the actual processing."""
        logger.info(
            "UPLOAD COMPLETE DURABLE QUEUE | JOB=%s | FILE=%s | chunks=%s",
            job_id,
            filename,
            total_chunks,
        )

    upload_module._run_assembly_and_etl = _durable_worker_noop
    _INSTALLED = True
    logger.info(
        "Installed durable upload queue patch; chunk completion no longer starts a second ETL path."
    )
