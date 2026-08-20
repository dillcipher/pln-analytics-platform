from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):

    UPLOADED = "UPLOADED"

    DETECTING = "DETECTING"

    VALIDATING = "VALIDATING"

    MERGING = "MERGING"

    TRANSFORMING = "TRANSFORMING"

    EXPORTING = "EXPORTING"

    FINISHED = "FINISHED"

    FAILED = "FAILED"