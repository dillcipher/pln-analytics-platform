from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.database.warehouse import Warehouse


class DuckDBExporter:

    @classmethod
    def export(
        cls,
        dataframe: pd.DataFrame,
        table: str,
    ):

        connection = Warehouse.connect()

        connection.register(
            "temp_dataframe",
            dataframe,
        )

        connection.execute(
            f"""
            INSERT INTO {table}

            SELECT *

            FROM temp_dataframe
            """
        )

        connection.unregister(
            "temp_dataframe"
        )

        connection.close()