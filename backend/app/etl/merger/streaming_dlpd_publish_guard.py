"""Safety guard for streaming DLPD publication.

Only months produced by the current source job are replaced. Existing months
from previous uploads remain untouched, which is required for a dashboard
that accumulates multiple business months over time.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import app.etl.merger.streaming_dlpd_merger_patch as streaming

logger = logging.getLogger(__name__)
_INSTALLED = False


def _month_from_path(path: Path) -> str:
    parts = path.stem.split("_")
    if len(parts) >= 3 and parts[-1].startswith("part"):
        return parts[-2]
    return ""


def install_streaming_dlpd_publish_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    def safe_publish(
        output_dir: Path,
        dataset: str,
        staged_files: list[Path],
    ) -> dict[str, Path]:
        folder = Path(output_dir) / "dlpd"
        folder.mkdir(parents=True, exist_ok=True)

        prefix = (
            "dlpd_pascabayar_"
            if dataset == "DLPD_PASCABAYAR"
            else "dlpd_prabayar_"
        )

        months = {
            month
            for month in (_month_from_path(path) for path in staged_files)
            if month
        }
        if not months:
            raise RuntimeError(
                f"Cannot publish DLPD {dataset}: staged files contain no valid months."
            )

        prepared: list[tuple[Path, Path]] = []

        # Move rather than copy: staging and production are on the same
        # processed filesystem, so this avoids a temporary 2x disk footprint.
        for staged in staged_files:
            final = folder / staged.name
            hidden = folder / f".{staged.name}.new"
            os.replace(staged, hidden)
            prepared.append((hidden, final))

        # Replace only partitions represented by this source job. Other
        # business months remain available to the warehouse/dashboard.
        for month in months:
            for old in folder.glob(f"{prefix}{month}_part*.parquet"):
                old.unlink(missing_ok=True)

        published: dict[str, Path] = {}
        try:
            for hidden, final in prepared:
                os.replace(hidden, final)
                month = _month_from_path(final)
                if month:
                    published.setdefault(month, final)
        except Exception:
            for hidden, _final in prepared:
                hidden.unlink(missing_ok=True)
            raise

        logger.info(
            "DLPD PUBLISH COMPLETE | dataset=%s | replaced_months=%s | files=%s",
            dataset,
            sorted(months),
            len(prepared),
        )
        return published

    streaming._publish_staged_outputs = safe_publish
    _INSTALLED = True
    logger.info(
        "Installed month-preserving streaming DLPD publish guard."
    )
