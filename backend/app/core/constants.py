from __future__ import annotations

from pathlib import Path

# =====================================================
# PROJECT ROOT
# =====================================================

# backend/app/core/constants.py
#                 ↑
# parent[0] = core
# parent[1] = app
# parent[2] = backend
# parent[3] = pln-analytics-platform

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# =====================================================
# DATA ROOT
# =====================================================

DATA = PROJECT_ROOT / "data"

# =====================================================
# RAW DATA
# =====================================================

RAW = DATA / "raw"

RAW_UPLOAD = RAW / "incoming"

# =====================================================
# PROCESSED DATA
# =====================================================

PROCESSED = DATA / "processed"

PARQUET = PROCESSED / "parquet"

WAREHOUSE = PROCESSED / "warehouse.duckdb"

METADATA = PROCESSED / "metadata"

REGISTRY = METADATA / "registry.json"

# =====================================================
# PARQUET FOLDERS
# =====================================================

ANEV_PARQUET = PARQUET / "anev"

DLPD_PARQUET = PARQUET / "dlpd"

PENGECEKAN_PARQUET = PARQUET / "pengecekan"

# =====================================================
# CREATE DIRECTORIES
# =====================================================

for folder in (
    RAW_UPLOAD,
    ANEV_PARQUET,
    DLPD_PARQUET,
    PENGECEKAN_PARQUET,
    METADATA,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )