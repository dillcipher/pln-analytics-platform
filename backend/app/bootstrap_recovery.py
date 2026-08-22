from __future__ import annotations

"""Production compatibility hooks.

This module is imported from ``app.__init__`` before the API/ETL modules.
Keep it side-effect-light: it must not start background ETL or recovery work.
"""

import logging

logger = logging.getLogger(__name__)


def _install_month_resolution_compatibility() -> None:
    """Keep MonthResolver compatible with legacy callers.

    The canonical resolver requires ``dataset``. Older persisted jobs and
    compatibility code may still call ``resolve_months(path)``. Infer the
    dataset from the detector when it is omitted, then call the canonical
    implementation with the correct signature.
    """
    try:
        from app.etl.detector.detector import FileDetector
        from app.etl.detector.month_resolver import MonthResolver
    except Exception:
        logger.exception("Could not initialize month-resolution compatibility")
        return

    if getattr(MonthResolver, "_pln_month_compat_installed", False):
        return

    original = MonthResolver.resolve_months.__func__

    @classmethod
    def resolve_months_compat(cls, filepath, dataset=None):
        resolved_dataset = dataset
        if not resolved_dataset:
            resolved_dataset = FileDetector.detect(filepath)

        if not resolved_dataset:
            raise ValueError(
                f"Cannot resolve DLPD month: dataset could not be detected for {filepath}"
            )

        return original(cls, filepath, resolved_dataset)

    MonthResolver.resolve_months = resolve_months_compat
    MonthResolver._pln_month_compat_installed = True
    logger.info("MonthResolver compatibility installed")


_install_month_resolution_compatibility()
