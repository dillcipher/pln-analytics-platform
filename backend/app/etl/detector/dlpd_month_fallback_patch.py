"""Fail-safe DLPD month discovery.

Month discovery is only an optimisation used to expand one workbook into
monthly ETL groups. It must never be allowed to make the entire DLPD dataset
disappear when an Excel workbook cannot be inspected by the lightweight
pre-scan.

If discovery fails, the normal streaming DLPD merger can still read the
workbook and resolve MONTH row-by-row. In that case we deliberately create a
single unfiltered DLPD group (month=None). The streaming merger writes the
actual monthly partitions from the row-level MONTH values.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.application.etl.etl_orchestrator import ETLOrchestrator

logger = logging.getLogger(__name__)
_INSTALLED = False
_ORIGINAL_RESOLVE = ETLOrchestrator._resolve_dlpd_month_cache
_ORIGINAL_EXPAND = ETLOrchestrator._expand_processing_groups


def _is_valid(record: dict) -> bool:
    return (
        record.get("validation") in {"PASSED", "PENDING"}
        and bool(record.get("filename"))
    )


def _resolve_with_fallback(cls, grouped, job_folder):
    try:
        return _ORIGINAL_RESOLVE(
            grouped=grouped,
            job_folder=job_folder,
        )
    except Exception:
        logger.exception(
            "DLPD month pre-scan failed. Falling back to row-level MONTH resolution."
        )

        cache: dict[str, set[str]] = {}
        for (dataset, _group_month), files in grouped.items():
            if dataset not in {"DLPD_PASCABAYAR", "DLPD_PRABAYAR"}:
                continue
            for record in files:
                if not _is_valid(record):
                    continue
                filename = str(record.get("filename") or "")
                if filename:
                    cache[filename] = set()
        return cache


def _expand_with_fallback(cls, grouped, job_folder, dlpd_month_cache=None):
    expanded = _ORIGINAL_EXPAND(
        grouped=grouped,
        job_folder=job_folder,
        dlpd_month_cache=dlpd_month_cache,
    )

    # The original implementation intentionally drops a DLPD group when no
    # month was discovered and the manifest month is also None. That is safe
    # only when discovery is guaranteed to succeed. Our streaming merger can
    # resolve MONTH itself, so retain the source file as an unfiltered group.
    for (dataset, group_month), files in grouped.items():
        if dataset not in {"DLPD_PASCABAYAR", "DLPD_PRABAYAR"}:
            continue

        valid_files = [record for record in files if _is_valid(record)]
        if not valid_files:
            continue

        filenames = {str(record.get("filename")) for record in valid_files}
        already_present = any(
            item_dataset == dataset
            and bool(filenames.intersection(str(record.get("filename")) for record in item_files))
            for item_dataset, _item_month, item_files in expanded
        )

        if already_present:
            continue

        expanded.append((dataset, group_month, valid_files))
        logger.warning(
            "DLPD MONTH FALLBACK GROUP | dataset=%s | month=%s | files=%s",
            dataset,
            group_month,
            len(valid_files),
        )

    return expanded


def install_dlpd_month_fallback_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    ETLOrchestrator._resolve_dlpd_month_cache = classmethod(_resolve_with_fallback)
    ETLOrchestrator._expand_processing_groups = classmethod(_expand_with_fallback)
    _INSTALLED = True
    logger.info("Installed fail-safe DLPD month fallback patch.")
