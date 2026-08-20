"""
Guards against the ETL and backend's intentionally-duplicated
SUSPECT_CATEGORIES list (see backend/app/core/suspect_categories.py
docstring for why it's duplicated rather than imported) drifting apart.
Run in CI on every push so a category added to one side can't silently
go unmatched by the other.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.core.suspect_categories import SUSPECT_CATEGORIES as BACKEND_CATEGORIES  # noqa: E402
from etl.config.schema_registry import SUSPECT_CATEGORIES as ETL_CATEGORIES  # noqa: E402


def test_categories_are_identical():
    assert BACKEND_CATEGORIES == ETL_CATEGORIES, (
        "backend/app/core/suspect_categories.py has drifted from "
        "etl/config/schema_registry.py — update both."
    )


if __name__ == "__main__":
    test_categories_are_identical()
    print(f"PASS  categories in sync ({len(BACKEND_CATEGORIES)} categories)")
