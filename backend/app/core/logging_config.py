"""Centralized logging setup, called once from `app.main` at startup."""
from __future__ import annotations

import logging
import sys


def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    # Quiet down noisy third-party loggers unless we're actually debugging them.
    for noisy in ("uvicorn.access", "duckdb"):
        logging.getLogger(noisy).setLevel(logging.WARNING if not debug else logging.INFO)
