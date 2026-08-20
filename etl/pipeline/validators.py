"""
Validation
==========
Column-presence validation happens per-file inside each reader (see
`readers/base_reader.validate_required_columns`) so a problem can be
traced back to the exact file it came from. This module aggregates
those problems into one run-level report and applies the platform's
policy for what's fatal vs. a warning.

Policy: a missing required column is a WARNING, not a fatal error — an
enterprise monitoring platform should keep running and surface a
partial/degraded dataset rather than halt the whole monthly pipeline
because one upstream export dropped a column. Zero rows after
validation for a whole source type IS fatal, since that means nothing
downstream can render.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_warnings(self, problems: list[str]) -> None:
        self.warnings.extend(problems)

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def log_summary(self) -> None:
        for w in self.warnings:
            logger.warning("[VALIDATION] %s", w)
        for e in self.errors:
            logger.error("[VALIDATION] %s", e)
        logger.info(
            "Validation summary: %d warning(s), %d error(s)",
            len(self.warnings), len(self.errors),
        )


def require_non_empty(report: ValidationReport, dataset_name: str, row_count: int) -> None:
    if row_count == 0:
        report.add_error(f"{dataset_name}: produced 0 rows — refusing to write an empty dataset")
