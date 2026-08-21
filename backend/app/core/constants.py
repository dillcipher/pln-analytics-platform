from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# FastAPI Cloud instances have ephemeral local storage. The root paths can
# therefore be redirected to a mounted/persistent directory when available.
DATA = Path(
    os.getenv("DATA_ROOT_DIR", str(PROJECT_ROOT / "data"))
).expanduser()

RAW = Path(
    os.getenv("DATA_RAW_DIR", str(DATA / "raw"))
).expanduser()
RAW_UPLOAD = Path(
    os.getenv("DATA_INCOMING_DIR", str(RAW / "incoming"))
).expanduser()

PROCESSED = Path(
    os.getenv("DATA_PROCESSED_DIR", str(DATA / "processed"))
).expanduser()
PARQUET = PROCESSED / "parquet"
WAREHOUSE = PROCESSED / "warehouse.duckdb"
METADATA = PROCESSED / "metadata"
REGISTRY = METADATA / "registry.json"

ANEV_PARQUET = PARQUET / "anev"
DLPD_PARQUET = PARQUET / "dlpd"
PENGECEKAN_PARQUET = PARQUET / "pengecekan"
CUSTOMER_LOCATION_PARQUET = PARQUET / "customer_location"

for folder in (
    RAW_UPLOAD,
    ANEV_PARQUET,
    DLPD_PARQUET,
    PENGECEKAN_PARQUET,
    CUSTOMER_LOCATION_PARQUET,
    METADATA,
):
    folder.mkdir(parents=True, exist_ok=True)
