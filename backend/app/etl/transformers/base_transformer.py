from __future__ import annotations

import pandas as pd


class BaseTransformer:
    """
    Base Transformer.

    Common transformation utilities shared by all datasets.
    """

    @staticmethod
    def normalize_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe.columns = (
            dataframe.columns
            .astype(str)
            .str.strip()
            .str.upper()
        )

        return dataframe

    @staticmethod
    def clean_idpel(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if "IDPEL" not in dataframe.columns:

            return dataframe

        dataframe["IDPEL"] = (

            dataframe["IDPEL"]

            .fillna("")

            .astype(str)

            .str.strip()

        )

        dataframe = dataframe[
            dataframe["IDPEL"] != ""
        ]

        return dataframe

    @staticmethod
    def remove_duplicates(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if "IDPEL" in dataframe.columns:

            return dataframe.drop_duplicates(
                subset=["IDPEL"],
                keep="first",
            )

        return dataframe.drop_duplicates()

    @staticmethod
    def clean_strings(
        dataframe: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:

        for column in columns:

            if column not in dataframe.columns:

                continue

            dataframe[column] = (

                dataframe[column]

                .fillna("")

                .astype(str)

                .str.strip()

            )

        return dataframe

    @staticmethod
    def clean_numeric(
        dataframe: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:

        for column in columns:

            if column not in dataframe.columns:

                continue

            dataframe[column] = pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )

        return dataframe

    @staticmethod
    def clean_dates(
        dataframe: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:

        for column in columns:

            if column not in dataframe.columns:

                continue

            dataframe[column] = pd.to_datetime(
                dataframe[column],
                errors="coerce",
            )

        return dataframe

    @staticmethod
    def sort_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.reindex(
            sorted(dataframe.columns),
            axis=1,
        )

        return dataframe

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        raise NotImplementedError