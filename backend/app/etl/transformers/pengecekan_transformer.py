from __future__ import annotations

import pandas as pd

from app.etl.transformers.base_transformer import BaseTransformer


class PengecekanTransformer(BaseTransformer):
    """
    Pengecekan dataset transformer.

    Performs:
    - Column normalization
    - IDPEL cleaning
    - Duplicate removal
    - String normalization
    - Date conversion
    - Metadata normalization
    """

    STRING_COLUMNS = [
        "STATUS",
        "HASIL",
        "KETERANGAN",
    ]

    DATE_COLUMNS = [
        "WAKTU_PERIKSA",
        "TANGGAL_PERIKSA",
        "TGL_PERIKSA",
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

        dataframe = self.clean_strings(
            dataframe,
            self.STRING_COLUMNS,
        )

        dataframe = self.clean_dates(
            dataframe,
            self.DATE_COLUMNS,
        )

        # =====================================================
        # Status Normalization
        # =====================================================

        for column in self.STRING_COLUMNS:

            if column not in dataframe.columns:
                continue

            dataframe[column] = dataframe[column].str.upper()

        # =====================================================
        # Metadata
        # =====================================================

        if "DATASET" not in dataframe.columns:

            dataframe["DATASET"] = "PENGECEKAN"

        return dataframe