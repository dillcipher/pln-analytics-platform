"""Keep chunk-completion ETL on the explicit upload path.

Startup recovery is intentionally disabled by default in ``app.main`` because
large pending workbooks can otherwise create an OOM/restart loop. That does
not mean a newly completed upload should be left idle. The upload endpoint's
existing background assembly + ETL path is safe because it is triggered by an
explicit user upload and runs after the HTTP response is accepted.

This compatibility module therefore no longer replaces
``upload._run_assembly_and_etl`` with a no-op. It only records that the upload
path is the explicit ETL trigger.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_INSTALLED = False


def install_durable_upload_queue_patch() -> None:
    """Install compatibility behavior without disabling upload processing."""
    global _INSTALLED
    if _INSTALLED:
        return

    logger.info(
        "Upload completion keeps its explicit background assembly + ETL path; "
        "startup recovery remains opt-in."
    )
    _INSTALLED = True
