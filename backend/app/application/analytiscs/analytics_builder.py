from __future__ import annotations

import logging

import pandas as pd

from app.core.constants import PARQUET
from app.database.warehouse import Warehouse

logger = logging.getLogger(__name__)


class AnalyticsBuilder:
    """
    Build analytics datasets from warehouse facts.

    Output:

    - executive_kpis
    - dlpd_customer
    - suspect_main
    - suspect_summary
    - suspect_detail
    """

    @classmethod
    def build(cls) -> None:

        logger.info("=" * 80)
        logger.info("BUILDING ANALYTICS DATASETS")
        logger.info("=" * 80)

        conn = Warehouse.connect()

        try:

            cls._build_executive(conn)

            cls._build_dlpd(conn)

            cls._build_suspect(conn)

            logger.info("=" * 80)
            logger.info("ANALYTICS BUILD FINISHED")
            logger.info("=" * 80)

        finally:

            conn.close()