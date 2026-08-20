from __future__ import annotations

import pandas as pd

from app.etl.transformers.base_transformer import BaseTransformer


class ANEVTransformer(BaseTransformer):
    """
    ANEV dataset transformer.

    Performs:
    - Column normalization
    - IDPEL cleaning
    - Duplicate removal
    - Date conversion
    - Numeric conversion
    - Metadata normalization
    """

    NUMERIC_COLUMNS = [
        "CURRENT_L1",
        "CURRENT_L2",
        "CURRENT_L3",
        "CURRENT_N",
        "POWER",
    ]

    DATE_COLUMNS = [
        "READ_DATE",
    ]

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        # =====================================================
        # Base Cleaning
        # =====================================================

        dataframe = self.normalize_columns(
            dataframe,
        )

        dataframe = self.clean_idpel(
            dataframe,
        )

        dataframe = self.remove_duplicates(
            dataframe,
        )

        # =====================================================
        # Data Cleaning
        # =====================================================

        dataframe = self.clean_dates(
            dataframe,
            self.DATE_COLUMNS,
        )

        dataframe = self.clean_numeric(
            dataframe,
            self.NUMERIC_COLUMNS,
        )

        # =====================================================
        # Metadata
        # =====================================================

        if "DATASET" not in dataframe.columns:

            dataframe["DATASET"] = "ANEV"

        return dataframe