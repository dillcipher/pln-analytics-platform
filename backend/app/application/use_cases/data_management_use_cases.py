from __future__ import annotations

from app.infrastructure.duckdb.data_management_repository import (
    DuckDbDataManagementRepository,
)


# ==========================================================
# OVERVIEW
# ==========================================================

class GetDataManagementOverview:

    def __init__(
        self,
        repository=None,
    ):
        self.repository = (
            repository
            or DuckDbDataManagementRepository()
        )

    def execute(self):
        return self.repository.overview()


# ==========================================================
# CATALOG
# ==========================================================

class GetDataManagementCatalog:

    def __init__(
        self,
        repository=None,
    ):
        self.repository = (
            repository
            or DuckDbDataManagementRepository()
        )

    def execute(self):
        return self.repository.catalog()


# ==========================================================
# FILTER OPTIONS
# ==========================================================

class GetDataManagementFilterOptions:

    def __init__(
        self,
        repository=None,
    ):
        self.repository = (
            repository
            or DuckDbDataManagementRepository()
        )

    def execute(
        self,
        dataset: str,
        month: str | None = None,
    ):
        return self.repository.filter_options(
            dataset,
            month,
        )


# ==========================================================
# PREVIEW
# ==========================================================

class PreviewDataManagement:

    def __init__(
        self,
        repository=None,
    ):
        self.repository = (
            repository
            or DuckDbDataManagementRepository()
        )

    def execute(
        self,
        dataset,
        month=None,
        filters=None,
        limit=100,
    ):
        return self.repository.preview(
            dataset,
            month,
            filters or {},
            limit,
        )


# ==========================================================
# EXPORT
# ==========================================================

class ExportDataManagement:

    def __init__(
        self,
        repository=None,
    ):
        self.repository = (
            repository
            or DuckDbDataManagementRepository()
        )

    def execute(
        self,
        dataset,
        month=None,
        filters=None,
        columns=None,
    ):
        return self.repository.export_csv(
            dataset,
            month,
            filters or {},
            columns,
        )


# ==========================================================
# STATUS
# ==========================================================

class GetDataManagementStatus:

    def __init__(
        self,
        repository=None,
    ):
        self.repository = (
            repository
            or DuckDbDataManagementRepository()
        )

    def execute(self):
        return self.repository.status()