"""Correct DLPD transformation ordering.

The legacy transformer removed duplicate IDPEL values before resolving MONTH.
That is unsafe when one workbook contains the same customer in several
business months: later months were silently discarded. This patch preserves
the existing business rules but performs deduplication after MONTH is known,
using (IDPEL, MONTH) as the natural partition key.
"""

from __future__ import annotations

from app.etl.transformers.dlpd_transformer import DLPDTransformer

_INSTALLED = False


def _transform(self, dataframe):
    dataframe = self.normalize_columns(dataframe)
    dataframe = self.clean_idpel(dataframe)
    dataframe = self.clean_strings(dataframe, self.STRING_COLUMNS)
    dataframe = self.clean_numeric(dataframe, self.NUMERIC_COLUMNS)
    dataframe = self.clean_dates(dataframe, self.DATE_COLUMNS)

    if "THBL" not in dataframe.columns:
        dataframe["THBL"] = ""
    if "THBLREK" not in dataframe.columns:
        dataframe["THBLREK"] = ""

    dataframe["THBL"] = dataframe["THBL"].fillna("").astype(str).str.strip()
    dataframe["THBLREK"] = dataframe["THBLREK"].fillna("").astype(str).str.strip()

    dataframe["MONTH"] = self._resolve_month_per_row(dataframe)
    dataframe["MONTH"] = (
        dataframe["MONTH"]
        .apply(self._normalize_month_value)
        .fillna("")
        .astype(str)
        .str.strip()
    )

    if "DATASET" not in dataframe.columns:
        dataframe["DATASET"] = "DLPD"
    dataframe["DATASET"] = (
        dataframe["DATASET"].fillna("DLPD").astype(str).str.strip()
    )

    # A customer may legitimately occur once in each business month.
    # Deduplicate only inside the same month, after MONTH is resolved.
    if "IDPEL" in dataframe.columns and "MONTH" in dataframe.columns:
        before = len(dataframe)
        dataframe = dataframe.drop_duplicates(
            subset=["IDPEL", "MONTH"],
            keep="first",
        ).copy()
        removed = before - len(dataframe)
        if removed:
            import logging
            logging.getLogger(__name__).info(
                "DLPD duplicate rows removed after month resolution: %s",
                removed,
            )

    return dataframe


def install_dlpd_transformer_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    DLPDTransformer.transform = _transform
    _INSTALLED = True
