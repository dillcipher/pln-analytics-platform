from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.application.jobs.job_status import JobStatus


class JobManager:

    @staticmethod
    def update(
        job_folder: Path,
        *,
        status: JobStatus,
        progress: int,
        step: str,
    ):

        manifest = job_folder / "manifest.json"

        with open(
            manifest,
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        data["status"] = status
        data["progress"] = progress
        data["current_step"] = step

        if progress > 0 and data["started_at"] is None:
            data["started_at"] = datetime.now().isoformat()

        if progress >= 100:
            data["finished_at"] = datetime.now().isoformat()

        with open(
            manifest,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
            )