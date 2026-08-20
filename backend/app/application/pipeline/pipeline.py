from __future__ import annotations

import logging
import time
from pathlib import Path

from app.application.etl.etl_orchestrator import ETLOrchestrator

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Main ETL Pipeline.

    Flow
    ----
    Upload
        ↓
    Manifest
        ↓
    ETL Orchestrator
        ↓
    Export
        ↓
    Registry Update
    """

    @classmethod
    def run(
        cls,
        job_folder: Path,
    ):

        logger.info("-" * 80)
        logger.info("Pipeline started")

        started = time.perf_counter()

        result = ETLOrchestrator.process(
            job_folder
        )

        duration = round(
            time.perf_counter() - started,
            2,
        )

        logger.info(
            "Pipeline finished (%s sec)",
            duration,
        )

        logger.info("-" * 80)

        return {
            "success": True,
            "duration_seconds": duration,
            "result": result,
        }