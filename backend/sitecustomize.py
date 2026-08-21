"""Runtime guard for Excel files assembled from chunked uploads.

Python imports ``sitecustomize`` automatically when this directory is on
sys.path.  The guard is intentionally narrow: it only affects Excel files
under the raw incoming upload tree.  It waits until the file is stable and
has a valid ZIP container before pandas is allowed to open it.
"""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path


try:
    import pandas as _pd

    _OriginalExcelFile = _pd.ExcelFile

    _INCOMING_MARKERS = (
        os.path.normpath("/app/data/raw/incoming"),
        os.path.normpath("data/raw/incoming"),
    )

    def _is_incoming_excel(path) -> bool:
        try:
            resolved = os.path.abspath(os.fspath(path))
        except (TypeError, ValueError, OSError):
            return False

        return any(
            resolved == marker
            or resolved.startswith(marker + os.sep)
            for marker in _INCOMING_MARKERS
        )

    def _wait_for_complete_excel(path) -> None:
        """Wait for a chunk-assembled XLSX/XLSM to become readable.

        Assembly writes to a temporary file and normally exposes the final
        name only after completion. This guard is a second line of defence
        for recovery races already present in older jobs: if ETL observes a
        final filename while it is still being assembled, do not let pandas
        open the partial ZIP.
        """

        try:
            suffix = Path(path).suffix.lower()
        except (TypeError, ValueError, OSError):
            return

        if suffix not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
            return

        if not _is_incoming_excel(path):
            return

        deadline = time.monotonic() + float(
            os.getenv("EXCEL_ASSEMBLY_WAIT_SECONDS", "180")
        )
        previous = None
        stable_since = None

        while time.monotonic() < deadline:
            try:
                stat = os.stat(path)
                size = stat.st_size
                mtime_ns = stat.st_mtime_ns
            except FileNotFoundError:
                time.sleep(0.5)
                continue
            except OSError:
                time.sleep(0.5)
                continue

            current = (size, mtime_ns)
            if current != previous:
                previous = current
                stable_since = time.monotonic()
                time.sleep(0.5)
                continue

            # Require a short period with no writes before testing the ZIP.
            if stable_since is None or time.monotonic() - stable_since < 0.75:
                time.sleep(0.25)
                continue

            try:
                with zipfile.ZipFile(path, "r") as archive:
                    bad_member = archive.testzip()
                if bad_member is None:
                    return
            except (zipfile.BadZipFile, OSError):
                pass

            time.sleep(0.75)

        raise RuntimeError(
            f"Excel assembly did not become a valid workbook within "
            f"{os.getenv('EXCEL_ASSEMBLY_WAIT_SECONDS', '180')}s: {path}"
        )

    def _SafeExcelFile(path_or_buffer, *args, **kwargs):
        if isinstance(path_or_buffer, (str, os.PathLike)):
            _wait_for_complete_excel(path_or_buffer)
        return _OriginalExcelFile(path_or_buffer, *args, **kwargs)

    _pd.ExcelFile = _SafeExcelFile

except Exception as _exc:
    # Never prevent application startup because of the defensive guard.
    print(f"WARNING: Excel assembly guard unavailable: {_exc!r}")
