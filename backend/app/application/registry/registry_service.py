from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import duckdb

from app.core.constants import METADATA

logger = logging.getLogger(__name__)


class RegistryService:
    """
    Registry metadata seluruh dataset hasil ETL.

    Menyimpan:
    - dataset
    - period
    - parquet path
    - row count
    - column count
    - updated time
    """

    REGISTRY_FILE = METADATA / "registry.json"

    @classmethod
    def _load(cls) -> list[dict]:

        if not cls.REGISTRY_FILE.exists():

            return []

        with open(
            cls.REGISTRY_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            return json.load(f)

    @classmethod
    def _save(
        cls,
        registry: list[dict],
    ) -> None:

        METADATA.mkdir(
            parents=True,
            exist_ok=True,
        )

        registry.sort(
            key=lambda x: (
                x["dataset"],
                str(x["period"]),
            )
        )

        with open(
            cls.REGISTRY_FILE,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                registry,
                f,
                indent=4,
                ensure_ascii=False,
            )

    @classmethod
    def update(
        cls,
        dataset: str,
        period: str | None,
        parquet_file: Path,
    ) -> None:

        if not parquet_file.exists():

            raise FileNotFoundError(
                parquet_file,
            )

        connection = duckdb.connect()

        try:

            rows = connection.execute(
                f"""
                SELECT COUNT(*)

                FROM read_parquet(
                    '{parquet_file.as_posix()}'
                )
                """
            ).fetchone()[0]

            columns = len(
                connection.execute(
                    f"""
                    DESCRIBE

                    SELECT *

                    FROM read_parquet(
                        '{parquet_file.as_posix()}'
                    )
                    """
                ).fetchall()
            )

        finally:

            connection.close()

        registry = cls._load()

        registry = [

            item

            for item in registry

            if not (

                item["dataset"] == dataset

                and item["period"] == period

            )

        ]

        registry.append(
            {
                "dataset": dataset,
                "period": period,
                "rows": rows,
                "columns": columns,
                "file": parquet_file.name,
                "path": str(
                    parquet_file.resolve(),
                ),
                "updated_at": datetime.now().isoformat(),
            }
        )

        cls._save(
            registry,
        )

        logger.info(
            "Registry updated : %s (%s)",
            dataset,
            period,
        )

    @classmethod
    def get_registry(
        cls,
    ) -> list[dict]:

        return cls._load()

    @classmethod
    def get_dataset(
        cls,
        dataset: str,
    ) -> list[dict]:

        return [

            item

            for item in cls._load()

            if item["dataset"] == dataset

        ]

    @classmethod
    def get_period(
        cls,
        dataset: str,
        period: str | None,
    ) -> dict | None:

        for item in cls._load():

            if (

                item["dataset"] == dataset

                and item["period"] == period

            ):

                return item

        return None

    @classmethod
    def remove(
        cls,
        dataset: str,
        period: str | None,
    ) -> None:

        registry = [

            item

            for item in cls._load()

            if not (

                item["dataset"] == dataset

                and item["period"] == period

            )

        ]

        cls._save(
            registry,
        )

    @classmethod
    def clear(
        cls,
    ) -> None:

        cls._save(
            [],
        )