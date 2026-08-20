"""
The nine Suspect Analytics anomaly categories, matching the Summary
Page column spec exactly.

This list is intentionally duplicated from `etl/config/schema_registry.py`
rather than imported from it: the ETL package and the backend are
deployed as two SEPARATE environments (Google Colab vs. Render — see the
architecture doc's security section, "Separate ETL environment from
Dashboard environment"), so the backend container never has the `etl/`
package available at runtime. If this list changes, update both places —
`tests/etl/test_pipeline.py` and this module's own smoke test both assert
the two lists stay in sync during local development.
"""
from __future__ import annotations

SUSPECT_CATEGORIES: tuple[str, ...] = (
    "ASYMMETRIC POWER BY INSTANT",
    "INCORRECT PHASE BY INSTANT",
    "OVER CURRENT BY INSTANT",
    "OVER VOLTAGE BY INSTANT",
    "REVERSAL BY INSTANT",
    "TIME DIFFERENCE - INSTANT",
    "UNBALANCE CURRENT BY INSTANT",
    "UNDER VOLTAGE BY INSTANT",
    "VOLTAGE DIP - INSTANT",
)
