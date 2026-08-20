from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict


class FileGrouper:
    """
    Group uploaded files by dataset and business month.

    Coordinate masters
    ------------------
    TO_PRABAYAR.xlsx and TO_PASCABAYAR.xlsx are intentionally
    monthless. They therefore form a CUSTOMER_LOCATION/None group.

    The ETL orchestrator consumes that group as a fixed coordinate
    master and must never export it as a monthly parquet.

    No month is inferred or changed here. MonthResolver is the
    single source of truth for month resolution.
    """

    @staticmethod
    def group(
        files: list[dict],
    ) -> dict[tuple[str | None, str | None], list[dict]]:
        grouped: DefaultDict[
            tuple[str | None, str | None],
            list[dict],
        ] = defaultdict(list)

        for file in files:

            dataset = file.get("dataset")
            month = file.get("month")

            # --------------------------------------------------
            # Invalid records are retained in their own group
            # instead of causing a KeyError and crashing the ETL.
            # The orchestrator will reject/skip them.
            # --------------------------------------------------

            key = (
                dataset,
                month,
            )

            grouped[key].append(file)

        return dict(grouped)