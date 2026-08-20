from __future__ import annotations
from pydantic import BaseModel, Field

class ExportColumn(BaseModel):
    key: str
    label: str
    dtype: str

class ExportDataset(BaseModel):
    key: str
    label: str
    group: str
    description: str
    source: str
    columns: list[ExportColumn] = Field(default_factory=list)
    filter_keys: list[str] = Field(default_factory=list)

class ExportFilterOption(BaseModel):
    key: str
    label: str
    values: list[str] = Field(default_factory=list)

class ExportPreviewResponse(BaseModel):
    dataset: str
    columns: list[ExportColumn] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    total_rows: int

class WarehouseDatasetStatus(BaseModel):
    name: str
    rows: int
    size_bytes: int
    available: bool

class DataManagementStatusResponse(BaseModel):
    datasets: list[WarehouseDatasetStatus] = Field(default_factory=list)
    total_datasets: int
    total_rows: int
    total_size_bytes: int
