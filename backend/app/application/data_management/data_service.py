from __future__ import annotations

from app.application.registry.registry_service import RegistryService


class DataManagementService:
    """
    Business layer for dataset management.
    """

    @classmethod
    def overview(cls):

        datasets = RegistryService.get_registry()

        total_dataset = len(datasets)

        total_rows = sum(
            d["rows"]
            for d in datasets
        )

        total_size = round(
            sum(
                d["size_mb"]
                for d in datasets
            ),
            2,
        )

        return {

            "total_dataset": total_dataset,

            "total_rows": total_rows,

            "total_size_mb": total_size,

            "datasets": datasets,

        }