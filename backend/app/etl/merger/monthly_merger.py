from __future__ import annotations
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from app.etl.transformers.anev_transformer import ANEVTransformer
from app.etl.transformers.customer_location_transformer import (
    CustomerLocationTransformer,
)
from app.etl.transformers.dlpd_transformer import DLPDTransformer
from app.etl.transformers.pengecekan_transformer import (
    PengecekanTransformer,
)
from app.etl.validator.validator import DatasetValidator


logger = logging.getLogger(__name__)


class MonthlyMerger:
    """
    Merge uploaded datasets into parquet files.

    Coordinate architecture
    -----------------------
    TO_PRABAYAR.xlsx and TO_PASCABAYAR.xlsx are the authoritative
    coordinate masters.

    Coordinate flow:

        TO_PRABAYAR / TO_PASCABAYAR
                    |
                    v
        CUSTOMER_LOCATION monthly master
                    |
                    | JOIN IDPEL
                    v
             DLPD PRA / PASCA
                    |
                    v
             KOORDINAT_X/Y

    Coordinate rules:

    1. LATITUDE  -> KOORDINAT_X
    2. LONGITUDE -> KOORDINAT_Y
    3. IDPEL is the only customer matching key.
    4. Existing DLPD coordinates are not authoritative.
    5. Missing coordinate matches remain NULL/empty.
    6. No coordinate is guessed.
    """

    # ==========================================================
    # TRANSFORMERS
    # ==========================================================

    TRANSFORMERS = {
        "ANEV": ANEVTransformer(),

        "DLPD_PASCABAYAR": DLPDTransformer(),

        "DLPD_PRABAYAR": DLPDTransformer(),

        "PENGECEKAN": PengecekanTransformer(),

        "CUSTOMER_LOCATION": CustomerLocationTransformer(),
    }

    # ==========================================================
    # OUTPUT FOLDERS
    # ==========================================================

    DATASET_FOLDERS = {
        "ANEV": "anev",

        "DLPD_PASCABAYAR": "dlpd",

        "DLPD_PRABAYAR": "dlpd",

        "PENGECEKAN": "pengecekan",

        "CUSTOMER_LOCATION": "customer_location",
    }

    # ==========================================================
    # DATASET TYPES THAT REQUIRE COORDINATES
    # ==========================================================

    COORDINATE_DATASETS = {
        "DLPD_PASCABAYAR",
        "DLPD_PRABAYAR",
    }

    # ==========================================================
    # DATAFRAME COLUMN NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_dataframe_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize dataframe column names while preserving semantic
        underscores.

        Examples:

            KOORDINAT_X -> KOORDINAT_X
            KOORDINAT_Y -> KOORDINAT_Y
            UNITUPI     -> UNITUPI
        """

        dataframe = dataframe.copy()

        dataframe.columns = (
            dataframe.columns
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # ------------------------------------------------------
        # Coordinate master schema
        # ------------------------------------------------------

        if (
            "KOORDINAT_X" not in dataframe.columns
            and "LATITUDE" in dataframe.columns
        ):
            dataframe["KOORDINAT_X"] = (
                dataframe["LATITUDE"]
            )

        if (
            "KOORDINAT_Y" not in dataframe.columns
            and "LONGITUDE" in dataframe.columns
        ):
            dataframe["KOORDINAT_Y"] = (
                dataframe["LONGITUDE"]
            )

        return dataframe

    # ==========================================================
    # IDPEL NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_idpel_series(
        series: pd.Series,
    ) -> pd.Series:
        """
        Normalize IDPEL consistently across DLPD and coordinate masters.

        Excel/Pandas can represent an IDPEL as:
            171002615379
            171002615379.0
            1.71002615379E+11

        A direct astype(str) comparison makes those values different even
        though they represent the same customer. This helper normalizes
        only formatting artifacts; it does not invent or alter real IDs.
        """

        def normalize(value) -> str:
            if pd.isna(value):
                return ""

            value = str(value).strip()

            if not value:
                return ""

            # Remove Excel/Pandas integer suffix such as "12345.0".
            if re.fullmatch(r"[+-]?\\d+\\.0+", value):
                return value.split(".", 1)[0]

            # Normalize scientific notation only when it represents an
            # integer IDPEL. Leading zeros in ordinary string IDs are kept.
            if "e" in value.lower():
                try:
                    number = Decimal(value)
                    if number == number.to_integral_value():
                        return format(number.quantize(Decimal("1")), "f")
                except (InvalidOperation, ValueError):
                    pass

            return value

        return series.apply(normalize).astype(str).str.strip()

    # ==========================================================
    # COORDINATE SOURCE PRIORITY
    # ==========================================================

    @staticmethod
    def _coordinate_source_priority(
        filename: str,
    ) -> int:
        """
        Coordinate source priority.

        30 = TO_PRABAYAR / TO_PASCABAYAR
        20 = DIL_SALDO_MASK
        10 = other CUSTOMER_LOCATION sources

        TO is authoritative.
        """

        normalized = (
            Path(filename)
            .name
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        while "__" in normalized:
            normalized = normalized.replace(
                "__",
                "_",
            )

        if (
            "to_prabayar" in normalized
            or "to_pascabayar" in normalized
        ):
            return 30

        if (
            "dil_saldo_mask" in normalized
            or "dil_saldo" in normalized
        ):
            return 20

        return 10

    # ==========================================================
    # VALID COORDINATE MASK
    # ==========================================================

    @staticmethod
    def _valid_coordinate_mask(
        dataframe: pd.DataFrame,
    ) -> pd.Series:
        """
        Return rows containing both coordinate values.

        This intentionally checks presence rather than attempting
        to invent/fix coordinates at merge time.
        """

        if (
            "KOORDINAT_X" not in dataframe.columns
            or "KOORDINAT_Y" not in dataframe.columns
        ):
            return pd.Series(
                False,
                index=dataframe.index,
            )

        x = pd.to_numeric(
            dataframe["KOORDINAT_X"],
            errors="coerce",
        )

        y = pd.to_numeric(
            dataframe["KOORDINAT_Y"],
            errors="coerce",
        )

        return (
            x.notna()
            & y.notna()
        )

    # ==========================================================
    # CUSTOMER LOCATION MASTER
    # ==========================================================

    @staticmethod
    def _merge_customer_locations(
        transformed_frames: list[
            tuple[pd.DataFrame, str, int]
        ],
    ) -> pd.DataFrame:
        """
        Merge CUSTOMER_LOCATION sources by IDPEL.

        Source priority:

            TO = 30
            DIL = 20
            other = 10

        A valid coordinate always beats an invalid coordinate.

        For equal coordinate validity, higher source priority wins.
        """

        if not transformed_frames:
            return pd.DataFrame()

        frames: list[pd.DataFrame] = []

        for (
            dataframe,
            source_file,
            priority,
        ) in transformed_frames:

            if dataframe is None or dataframe.empty:
                continue

            frame = dataframe.copy()

            if "IDPEL" not in frame.columns:
                logger.warning(
                    "Skipping CUSTOMER_LOCATION source "
                    "without IDPEL: %s",
                    source_file,
                )
                continue

            frame["_COORDINATE_SOURCE_FILE"] = (
                source_file
            )

            frame["_COORDINATE_SOURCE_PRIORITY"] = (
                priority
            )

            frames.append(frame)

        if not frames:
            return pd.DataFrame()

        merged = pd.concat(
            frames,
            ignore_index=True,
        )

        # ------------------------------------------------------
        # IDPEL
        # ------------------------------------------------------

        merged["IDPEL"] = (
            MonthlyMerger._normalize_idpel_series(
                merged["IDPEL"]
            )
        )

        merged = merged[
            merged["IDPEL"].ne("")
        ].copy()

        # ------------------------------------------------------
        # Coordinate validity
        # ------------------------------------------------------

        merged["_HAS_VALID_COORDINATE"] = (
            MonthlyMerger
            ._valid_coordinate_mask(merged)
            .astype(int)
        )

        # ------------------------------------------------------
        # Priority
        # ------------------------------------------------------

        merged = merged.sort_values(
            by=[
                "_HAS_VALID_COORDINATE",
                "_COORDINATE_SOURCE_PRIORITY",
            ],
            ascending=[
                False,
                False,
            ],
            kind="stable",
        )

        before = len(merged)

        merged = merged.drop_duplicates(
            subset=["IDPEL"],
            keep="first",
        ).copy()

        after = len(merged)

        logger.info(
            "CUSTOMER LOCATION coordinate master: "
            "%s rows -> %s unique IDPEL",
            before,
            after,
        )

        # ------------------------------------------------------
        # Source distribution
        # ------------------------------------------------------

        source_counts = (
            merged[
                "_COORDINATE_SOURCE_FILE"
            ]
            .value_counts()
            .to_dict()
        )

        logger.info(
            "CUSTOMER LOCATION selected sources: %s",
            source_counts,
        )

        coordinate_count = int(
            MonthlyMerger
            ._valid_coordinate_mask(merged)
            .sum()
        )

        logger.info(
            "CUSTOMER LOCATION valid coordinates: "
            "%s / %s",
            coordinate_count,
            len(merged),
        )

        # ------------------------------------------------------
        # Remove internal columns
        # ------------------------------------------------------

        merged = merged.drop(
            columns=[
                "_COORDINATE_SOURCE_FILE",
                "_COORDINATE_SOURCE_PRIORITY",
                "_HAS_VALID_COORDINATE",
            ],
            errors="ignore",
        )

        return merged

    # ==========================================================
    # LOAD COORDINATE MASTER
    # ==========================================================

    @staticmethod
    def _load_coordinate_master(
        month: str | None,
        output_dir: Path,
    ) -> pd.DataFrame:
        """
        Load the already-built monthly customer coordinate master.

        Expected file:

            data/processed/parquet/
                customer_location/
                    customer_location_<month>.parquet

        The master is produced from TO_PRABAYAR /
        TO_PASCABAYAR before DLPD coordinate enrichment.

        If the master does not exist, return an empty dataframe.

        The orchestrator is responsible for ensuring the master is
        created before DLPD processing.
        """

        if not month:
            logger.warning(
                "Cannot load coordinate master without month."
            )
            return pd.DataFrame()

        customer_location_dir = (
            output_dir
            / "customer_location"
        )

        # ======================================================
        # EXACT MONTH MASTER FIRST
        # ======================================================

        requested_month = str(
            month
        ).strip()

        master_path = (
            customer_location_dir
            / f"customer_location_{requested_month}.parquet"
        )

        if master_path.exists():

            logger.info(
                "Loading coordinate master "
                "(exact month %s): %s",
                requested_month,
                master_path,
            )

        else:

            # ==================================================
            # FALLBACK TO NEAREST AVAILABLE MASTER
            # ==================================================
            #
            # DLPD can contain historical months while the
            # available CUSTOMER_LOCATION master may only exist
            # for one or a few uploaded months.
            #
            # Exact month always wins.
            #
            # If the exact master does not exist, use the nearest
            # available monthly CUSTOMER_LOCATION master.
            #
            # This is NOT coordinate guessing. The coordinates
            # still come directly from CUSTOMER_LOCATION and are
            # joined by IDPEL.
            #
            # If a future upload creates the exact master, it will
            # automatically be preferred for that month.
            # ==================================================

            available_masters: list[
                tuple[str, Path]
            ] = []

            if customer_location_dir.exists():

                for candidate in customer_location_dir.glob(
                    "customer_location_*.parquet"
                ):

                    candidate_month = (
                        candidate.stem
                        .replace(
                            "customer_location_",
                            "",
                            1,
                        )
                        .strip()
                    )

                    if (
                        len(candidate_month) == 6
                        and candidate_month.isdigit()
                        and candidate_month.startswith("20")
                    ):

                        available_masters.append(
                            (
                                candidate_month,
                                candidate,
                            )
                        )

            if not available_masters:

                logger.warning(
                    "Coordinate master not found for %s "
                    "and no fallback CUSTOMER_LOCATION master "
                    "exists: %s",
                    requested_month,
                    customer_location_dir,
                )

                return pd.DataFrame()

            try:

                requested_number = int(
                    requested_month
                )

            except ValueError:

                logger.warning(
                    "Invalid coordinate master month: %s",
                    requested_month,
                )

                return pd.DataFrame()

            # --------------------------------------------------
            # Nearest business month.
            #
            # If equally close, prefer the older month.
            # --------------------------------------------------

            available_masters.sort(
                key=lambda item: (
                    abs(
                        int(item[0])
                        - requested_number
                    ),
                    int(item[0]),
                )
            )

            selected_month, master_path = (
                available_masters[0]
            )

            logger.warning(
                "Exact coordinate master not found "
                "for month %s. Using nearest available "
                "CUSTOMER_LOCATION master month %s: %s",
                requested_month,
                selected_month,
                master_path,
            )

        # ======================================================
        # READ PARQUET
        # ======================================================

        logger.info(
            "Loading coordinate master: %s",
            master_path,
        )

        try:

            master = pd.read_parquet(
                master_path,
            )

        except Exception:
            logger.exception(
                "Failed to read coordinate master: %s",
                master_path,
            )
            return pd.DataFrame()

        master = (
            MonthlyMerger
            ._normalize_dataframe_columns(
                master,
            )
        )

        required = {
            "IDPEL",
            "KOORDINAT_X",
            "KOORDINAT_Y",
        }

        missing = (
            required
            - set(master.columns)
        )

        if missing:
            logger.error(
                "Coordinate master missing columns: %s",
                sorted(missing),
            )
            return pd.DataFrame()

        master["IDPEL"] = (
            MonthlyMerger._normalize_idpel_series(
                master["IDPEL"]
            )
        )

        master = master[
            master["IDPEL"].ne("")
        ].copy()

        # ------------------------------------------------------
        # Ensure one coordinate row per IDPEL.
        # ------------------------------------------------------

        master["_HAS_VALID_COORDINATE"] = (
            MonthlyMerger
            ._valid_coordinate_mask(master)
            .astype(int)
        )

        master = master.sort_values(
            by="_HAS_VALID_COORDINATE",
            ascending=False,
            kind="stable",
        )

        master = master.drop_duplicates(
            subset=["IDPEL"],
            keep="first",
        ).copy()

        master = master.drop(
            columns=[
                "_HAS_VALID_COORDINATE",
            ],
            errors="ignore",
        )

        logger.info(
            "Coordinate master loaded: %s unique IDPEL",
            master["IDPEL"].nunique(),
        )

        return master[
            [
                "IDPEL",
                "KOORDINAT_X",
                "KOORDINAT_Y",
            ]
        ].copy()

    # ==========================================================
    # ENRICH DLPD WITH COORDINATES
    # ==========================================================

    @staticmethod
    def _enrich_with_coordinates(
        dataframe: pd.DataFrame,
        dataset: str,
        month: str | None,
        output_dir: Path,
    ) -> pd.DataFrame:
        """
        Enrich DLPD rows with authoritative coordinates.

        JOIN:

            DLPD.IDPEL
                LEFT JOIN
            CUSTOMER_LOCATION.IDPEL

        Only KOORDINAT_X and KOORDINAT_Y are taken from the
        coordinate master.

        Existing coordinate columns from DLPD are deliberately
        overwritten by the authoritative master when a match
        exists.

        Unmatched IDPEL remains without coordinates.
        """

        if dataset not in MonthlyMerger.COORDINATE_DATASETS:
            return dataframe

        dataframe = dataframe.copy()

        if "IDPEL" not in dataframe.columns:
            logger.warning(
                "Cannot enrich %s: IDPEL column missing.",
                dataset,
            )
            return dataframe

        coordinate_master = (
            MonthlyMerger._load_coordinate_master(
                month=month,
                output_dir=output_dir,
            )
        )

        if coordinate_master.empty:
            logger.warning(
                "No coordinate master available for "
                "%s / %s.",
                dataset,
                month,
            )

            # Ensure canonical columns still exist.
            if "KOORDINAT_X" not in dataframe.columns:
                dataframe["KOORDINAT_X"] = pd.NA

            if "KOORDINAT_Y" not in dataframe.columns:
                dataframe["KOORDINAT_Y"] = pd.NA

            return dataframe

        # ------------------------------------------------------
        # Normalize DLPD IDPEL
        # ------------------------------------------------------

        dataframe["IDPEL"] = (
            MonthlyMerger._normalize_idpel_series(
                dataframe["IDPEL"]
            )
        )

        coordinate_master["IDPEL"] = (
            MonthlyMerger._normalize_idpel_series(
                coordinate_master["IDPEL"]
            )
        )

        # ------------------------------------------------------
        # Remove existing coordinate columns from DLPD.
        #
        # The coordinate master is authoritative.
        # ------------------------------------------------------

        dataframe = dataframe.drop(
            columns=[
                "KOORDINAT_X",
                "KOORDINAT_Y",
                "LATITUDE",
                "LONGITUDE",
            ],
            errors="ignore",
        )

        # ------------------------------------------------------
        # PRE-JOIN DIAGNOSTIC
        # ------------------------------------------------------

        master_ids = set(
            coordinate_master["IDPEL"].dropna().astype(str)
        )
        dlpd_ids = set(
            dataframe["IDPEL"].dropna().astype(str)
        )
        intersection_count = len(dlpd_ids & master_ids)

        logger.info(
            "DLPD coordinate IDPEL diagnostic | "
            "dlpd_unique=%s | master_unique=%s | matched_unique=%s",
            len(dlpd_ids),
            len(master_ids),
            intersection_count,
        )

        # ------------------------------------------------------
        # LEFT JOIN
        # ------------------------------------------------------

        enriched = dataframe.merge(
            coordinate_master,
            on="IDPEL",
            how="left",
            validate="many_to_one",
        )

        # ------------------------------------------------------
        # Coordinate statistics
        # ------------------------------------------------------

        matched = (
            enriched["KOORDINAT_X"].notna()
            & enriched["KOORDINAT_Y"].notna()
        )

        total = len(enriched)
        matched_count = int(matched.sum())
        missing_count = total - matched_count

        coverage = (
            matched_count / total * 100
            if total
            else 0.0
        )

        logger.info(
            "=" * 80,
        )

        logger.info(
            "DLPD COORDINATE ENRICHMENT",
        )

        logger.info(
            "Dataset       : %s",
            dataset,
        )

        logger.info(
            "Month         : %s",
            month,
        )

        logger.info(
            "DLPD rows     : %s",
            total,
        )

        logger.info(
            "Coordinate hit: %s",
            matched_count,
        )

        logger.info(
            "Coordinate miss: %s",
            missing_count,
        )

        logger.info(
            "Coverage      : %.2f%%",
            coverage,
        )

        if matched_count == 0 and total > 0:
            logger.error(
                "DLPD coordinate enrichment produced ZERO matches | "
                "dataset=%s | month=%s | dlpd_unique=%s | "
                "master_unique=%s | matched_unique=%s",
                dataset,
                month,
                len(dlpd_ids),
                len(master_ids),
                intersection_count,
            )

        logger.info(
            "=" * 80,
        )

        return enriched

    # ==========================================================
    # DLPD COORDINATE ENRICHMENT PER ROW MONTH
    # ==========================================================

    @staticmethod
    def _enrich_dlp_per_row_month(
        dataframe: pd.DataFrame,
        dataset: str,
        output_dir: Path,
        fallback_month: str | None,
    ) -> pd.DataFrame:
        """
        Enrich DLPD coordinates using the MONTH calculated by
        DLPDTransformer for each row.

        IMPORTANT:
        A single DLPD Excel file can contain records belonging to
        different business months. Therefore the coordinate master
        MUST be selected from each row's MONTH, not from the
        manifest/group month.

        Example:

            row A -> MONTH 202605 -> customer_location_202605.parquet
            row B -> MONTH 202606 -> customer_location_202606.parquet

        Rows whose MONTH is blank use fallback_month only as a
        compatibility fallback. No coordinate is guessed.
        """

        if dataset not in MonthlyMerger.COORDINATE_DATASETS:
            return dataframe

        if dataframe.empty:
            return dataframe

        if "MONTH" not in dataframe.columns:
            dataframe = dataframe.copy()
            dataframe["MONTH"] = (
                fallback_month
                if fallback_month
                else ""
            )
            return MonthlyMerger._enrich_with_coordinates(
                dataframe=dataframe,
                dataset=dataset,
                month=fallback_month,
                output_dir=output_dir,
            )

        dataframe = dataframe.copy()

        # Normalize MONTH without changing the business meaning.
        dataframe["MONTH"] = (
            dataframe["MONTH"]
            .apply(DLPDTransformer._normalize_month_value)
            .fillna("")
            .astype(str)
            .str.strip()
        )

        result_parts: list[pd.DataFrame] = []

        # Process each business month independently so each row gets
        # the correct CUSTOMER_LOCATION master.
        for row_month, frame in dataframe.groupby(
            "MONTH",
            sort=True,
            dropna=False,
        ):
            row_month = str(row_month).strip()

            if row_month:
                enriched = MonthlyMerger._enrich_with_coordinates(
                    dataframe=frame.copy(),
                    dataset=dataset,
                    month=row_month,
                    output_dir=output_dir,
                )
            else:
                # No month means no authoritative monthly coordinate
                # master can safely be selected.
                enriched = frame.copy()

                if "KOORDINAT_X" not in enriched.columns:
                    enriched["KOORDINAT_X"] = pd.NA

                if "KOORDINAT_Y" not in enriched.columns:
                    enriched["KOORDINAT_Y"] = pd.NA

                logger.warning(
                    "DLPD rows without resolved MONTH: %s rows. "
                    "Coordinates left empty.",
                    len(enriched),
                )

            result_parts.append(enriched)

        if not result_parts:
            return dataframe

        # Preserve original row order as much as possible.
        result = pd.concat(
            result_parts,
            axis=0,
        ).sort_index()

        return result

    # ==========================================================
    # RESOLVE DLPD MONTH PER ROW
    # ==========================================================

    @staticmethod
    def _resolve_dlp_month_column(
        dataframe: pd.DataFrame,
        dataset: str,
    ) -> pd.DataFrame:
        """
        Ensure every DLPD row has a business MONTH before the
        monthly partition filter is applied.

        Rules
        -----
        1. Never overwrite an already-resolved MONTH.
        2. DLPD_PRABAYAR:
           - blank MONTH falls back to THBL.
        3. DLPD_PASCABAYAR:
           - blank MONTH falls back to THBLREK.
           - if THBLREK is unavailable, THBL is used as a
             compatibility fallback.
        4. No month is taken from the filename, JOB folder,
           upload date, or current date here.
        5. The manifest/group month remains the target partition
           filter; it does not overwrite row-level MONTH.

        This prevents a valid Prabayar file with THBL=202606 but
        an empty MONTH from being reduced to zero rows.
        """

        if dataset not in MonthlyMerger.COORDINATE_DATASETS:
            return dataframe

        dataframe = dataframe.copy()

        if "MONTH" not in dataframe.columns:
            dataframe["MONTH"] = ""

        dataframe["MONTH"] = (
            dataframe["MONTH"]
            .apply(DLPDTransformer._normalize_month_value)
            .fillna("")
            .astype(str)
            .str.strip()
        )

        blank_month = dataframe["MONTH"].eq("")

        if not blank_month.any():
            logger.info(
                "DLPD MONTH already resolved for all %s rows.",
                len(dataframe),
            )
            return dataframe

        if dataset == "DLPD_PRABAYAR":
            if "THBL" in dataframe.columns:
                resolved = (
                    dataframe["THBL"]
                    .apply(DLPDTransformer._normalize_month_value)
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

                dataframe.loc[blank_month, "MONTH"] = resolved.loc[
                    blank_month
                ]

        elif dataset == "DLPD_PASCABAYAR":
            resolved = pd.Series(
                "",
                index=dataframe.index,
                dtype="object",
            )

            if "THBLREK" in dataframe.columns:
                resolved = (
                    dataframe["THBLREK"]
                    .apply(DLPDTransformer._normalize_month_value)
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

            if "THBL" in dataframe.columns:
                thbl = (
                    dataframe["THBL"]
                    .apply(DLPDTransformer._normalize_month_value)
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

                resolved = resolved.mask(
                    resolved.eq(""),
                    thbl,
                )

            dataframe.loc[blank_month, "MONTH"] = resolved.loc[
                blank_month
            ]

        dataframe["MONTH"] = (
            dataframe["MONTH"]
            .apply(DLPDTransformer._normalize_month_value)
            .fillna("")
            .astype(str)
            .str.strip()
        )

        unresolved = int(dataframe["MONTH"].eq("").sum())

        logger.info(
            "DLPD MONTH RESOLUTION | dataset=%s | rows=%s | "
            "resolved=%s | unresolved=%s",
            dataset,
            len(dataframe),
            len(dataframe) - unresolved,
            unresolved,
        )

        if unresolved:
            logger.warning(
                "DLPD rows still without MONTH: %s rows | dataset=%s",
                unresolved,
                dataset,
            )

        return dataframe

    # ==========================================================
    # MAIN MERGE
    # ==========================================================

    @staticmethod
    def merge(
        dataset: str,
        month: str | None,
        files: list[Path],
        output_dir: Path,
    ) -> Path:
        """
        Merge one dataset/month into parquet.
        """

        logger.info(
            "Merging %s (%s files)",
            dataset,
            len(files),
        )

        if not files:
            raise ValueError(
                f"No files supplied for dataset '{dataset}'."
            )

        # ======================================================
        # CUSTOMER LOCATION
        # ======================================================

        if dataset == "CUSTOMER_LOCATION":

            transformer = (
                MonthlyMerger.TRANSFORMERS[
                    "CUSTOMER_LOCATION"
                ]
            )

            transformed_frames: list[
                tuple[pd.DataFrame, str, int]
            ] = []

            for file in files:

                logger.info(
                    "Reading CUSTOMER_LOCATION source: %s",
                    file.name,
                )

                sheet = (
                    DatasetValidator.get_sheet_name(
                        file,
                        dataset,
                    )
                )

                header = (
                    DatasetValidator.detect_header_row(
                        filepath=file,
                        sheet_name=sheet,
                    )
                )

                logger.info(
                    "Sheet : %s | Header : %s",
                    sheet,
                    header,
                )

                dataframe = pd.read_excel(
                    file,
                    sheet_name=sheet,
                    header=header,
                )

                logger.info(
                    "Original Columns [%s] : %s",
                    file.name,
                    list(dataframe.columns),
                )

                dataframe = (
                    MonthlyMerger
                    ._normalize_dataframe_columns(
                        dataframe,
                    )
                )

                logger.info(
                    "Normalized Columns [%s] : %s",
                    file.name,
                    list(dataframe.columns),
                )

                priority = (
                    MonthlyMerger
                    ._coordinate_source_priority(
                        file.name,
                    )
                )

                logger.info(
                    "Coordinate source priority [%s] : %s",
                    file.name,
                    priority,
                )

                transformed = transformer.transform(
                    dataframe,
                )

                transformed_frames.append(
                    (
                        transformed,
                        file.name,
                        priority,
                    )
                )

                logger.info(
                    "Transformed CUSTOMER_LOCATION [%s]: %s rows",
                    file.name,
                    len(transformed),
                )

            merged = (
                MonthlyMerger
                ._merge_customer_locations(
                    transformed_frames,
                )
            )

        # ======================================================
        # OTHER DATASETS
        # ======================================================

        else:

            dataframes: list[pd.DataFrame] = []

            for file in files:

                logger.info(
                    "Reading %s",
                    file,
                )

                sheet = (
                    DatasetValidator.get_sheet_name(
                        file,
                        dataset,
                    )
                )

                header = (
                    DatasetValidator.detect_header_row(
                        filepath=file,
                        sheet_name=sheet,
                    )
                )

                logger.info(
                    "Sheet : %s | Header : %s",
                    sheet,
                    header,
                )

                df = pd.read_excel(
                    file,
                    sheet_name=sheet,
                    header=header,
                )

                logger.info(
                    "Original Columns : %s",
                    list(df.columns),
                )

                # --------------------------------------------------
                # ETL COLUMN NORMALIZATION
                # --------------------------------------------------

                df = (
                    MonthlyMerger
                    ._normalize_dataframe_columns(
                        df,
                    )
                )

                logger.info(
                    "Normalized Columns : %s",
                    list(df.columns),
                )

                # --------------------------------------------------
                # SOURCE FILE
                # --------------------------------------------------

                df["SOURCE_FILE"] = file.name

                dataframes.append(
                    df
                )

            # ------------------------------------------------------
            # MERGE
            # ------------------------------------------------------

            merged = pd.concat(
                dataframes,
                ignore_index=True,
            )

            logger.info(
                "Merged rows : %s",
                len(merged),
            )

            # ------------------------------------------------------
            # TRANSFORM
            # ------------------------------------------------------

            transformer = (
                MonthlyMerger.TRANSFORMERS.get(
                    dataset,
                )
            )

            if transformer:

                logger.info(
                    "Transforming %s",
                    dataset,
                )

                merged = transformer.transform(
                    merged,
                )

            # ------------------------------------------------------
            # DLPD TARGET MONTH FILTER
            # ------------------------------------------------------
            #
            # A single DLPD source file may contain multiple business
            # months. The orchestrator calls this merger once for each
            # resolved month. Filter AFTER transformation so MONTH is
            # resolved per row before the partition is written.
            #
            # This is also what prevents the same complete DLPD file
            # from being exported seven times with all rows duplicated.
            # ------------------------------------------------------

            if dataset in MonthlyMerger.COORDINATE_DATASETS:

                # Resolve the row-level business month before the
                # target partition filter. Existing MONTH values are
                # preserved; only blank values are filled.
                merged = MonthlyMerger._resolve_dlp_month_column(
                    dataframe=merged,
                    dataset=dataset,
                )

                if month is not None:
                    target_month = (
                        DLPDTransformer._normalize_month_value(
                            month,
                        )
                    )

                    if target_month:
                        before_rows = len(merged)

                        merged = merged[
                            merged["MONTH"].eq(target_month)
                        ].copy()

                        logger.info(
                            "DLPD MONTH FILTER | %s | target=%s | %s -> %s rows",
                            dataset,
                            target_month,
                            before_rows,
                            len(merged),
                        )

            # ------------------------------------------------------
            # COORDINATE ENRICHMENT
            # ------------------------------------------------------
            #
            # IMPORTANT:
            #
            # This happens AFTER DLPD transformation.
            #
            # Therefore:
            #
            #   DLPD cleaning
            #       ↓
            #   IDPEL normalized
            #       ↓
            #   coordinate JOIN
            #
            # This prevents IDPEL formatting problems from
            # breaking the coordinate lookup.
            # ------------------------------------------------------

            merged = (
                MonthlyMerger
                ._enrich_dlp_per_row_month(
                    dataframe=merged,
                    dataset=dataset,
                    output_dir=output_dir,
                    fallback_month=month,
                )
            )

        # ======================================================
        # MONTH
        # ======================================================
        #
        # DLPDTransformer already resolved MONTH independently for
        # every row from:
        #
        #     THBL -> DLPD_TGLBACA -> THBLREK
        #
        # NEVER overwrite that result with the manifest/group month.
        #
        # Other datasets still receive the group month here.
        # ======================================================

        if dataset in MonthlyMerger.COORDINATE_DATASETS:
            if "MONTH" not in merged.columns:
                merged["MONTH"] = (
                    month
                    if month
                    else ""
                )

            merged["MONTH"] = (
                merged["MONTH"]
                .apply(DLPDTransformer._normalize_month_value)
                .fillna("")
                .astype(str)
                .str.strip()
            )

            logger.info(
                "DLPD MONTH values preserved per row: %s",
                sorted(
                    value
                    for value in merged["MONTH"].drop_duplicates().tolist()
                    if value
                ),
            )

        else:
            merged["MONTH"] = month

            logger.info(
                "MONTH assigned : %s",
                month,
            )

        # ======================================================
        # ENSURE COLUMN NAMES
        # ======================================================

        merged.columns = merged.columns.map(
            str,
        )

        # ======================================================
        # NORMALIZE OBJECT COLUMNS
        # ======================================================

        for column in merged.columns:

            if pd.api.types.is_object_dtype(
                merged[column],
            ):

                merged[column] = (
                    merged[column]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

        # ======================================================
        # CUSTOMER LOCATION DEBUG
        # ======================================================

        if dataset == "CUSTOMER_LOCATION":

            logger.info(
                "=" * 80,
            )

            logger.info(
                "CUSTOMER LOCATION COORDINATE CHECK",
            )

            logger.info(
                "Rows : %s",
                len(merged),
            )

            logger.info(
                "KOORDINAT_X exists : %s",
                "KOORDINAT_X" in merged.columns,
            )

            logger.info(
                "KOORDINAT_Y exists : %s",
                "KOORDINAT_Y" in merged.columns,
            )

            if "KOORDINAT_X" in merged.columns:

                logger.info(
                    "KOORDINAT_X filled : %s",
                    int(
                        merged[
                            "KOORDINAT_X"
                        ]
                        .notna()
                        .sum()
                    ),
                )

            if "KOORDINAT_Y" in merged.columns:

                logger.info(
                    "KOORDINAT_Y filled : %s",
                    int(
                        merged[
                            "KOORDINAT_Y"
                        ]
                        .notna()
                        .sum()
                    ),
                )

            if (
                "KOORDINAT_X" in merged.columns
                and "KOORDINAT_Y" in merged.columns
            ):

                logger.info(
                    "BOTH coordinates filled : %s",
                    int(
                        (
                            merged[
                                "KOORDINAT_X"
                            ].notna()
                            &
                            merged[
                                "KOORDINAT_Y"
                            ].notna()
                        ).sum()
                    ),
                )

                logger.info(
                    "Coordinate sample : %s",
                    merged[
                        [
                            "IDPEL",
                            "UNITUP",
                            "KOORDINAT_X",
                            "KOORDINAT_Y",
                        ]
                    ]
                    .head(5)
                    .to_dict("records"),
                )

            logger.info(
                "=" * 80,
            )

        # ======================================================
        # DLPD COORDINATE DEBUG
        # ======================================================

        if dataset in MonthlyMerger.COORDINATE_DATASETS:

            logger.info(
                "=" * 80,
            )

            logger.info(
                "FINAL DLPD COORDINATE CHECK",
            )

            logger.info(
                "Dataset : %s",
                dataset,
            )

            logger.info(
                "Month   : %s",
                month,
            )

            logger.info(
                "Rows    : %s",
                len(merged),
            )

            if (
                "KOORDINAT_X" in merged.columns
                and "KOORDINAT_Y" in merged.columns
            ):

                coordinate_mask = (
                    merged[
                        "KOORDINAT_X"
                    ].notna()
                    &
                    merged[
                        "KOORDINAT_Y"
                    ].notna()
                )

                logger.info(
                    "Rows with coordinates : %s",
                    int(coordinate_mask.sum()),
                )

                logger.info(
                    "Rows without coordinates : %s",
                    int(
                        (~coordinate_mask).sum()
                    ),
                )

                logger.info(
                    "Coordinate coverage : %.2f%%",
                    (
                        coordinate_mask.mean()
                        * 100
                        if len(merged)
                        else 0.0
                    ),
                )

                logger.info(
                    "Coordinate sample : %s",
                    merged[
                        [
                            "IDPEL",
                            "KOORDINAT_X",
                            "KOORDINAT_Y",
                        ]
                    ]
                    .head(5)
                    .to_dict("records"),
                )

            logger.info(
                "=" * 80,
            )

        # ======================================================
        # DLPD MONTH DISTRIBUTION
        # ======================================================

        if dataset in MonthlyMerger.COORDINATE_DATASETS:
            month_distribution = (
                merged["MONTH"]
                .value_counts(dropna=False)
                .sort_index()
                .to_dict()
                if "MONTH" in merged.columns
                else {}
            )

            logger.info(
                "DLPD MONTH distribution: %s",
                month_distribution,
            )

        # ======================================================
        # FINAL DATAFRAME DEBUG
        # ======================================================

        logger.info(
            "=" * 80,
        )

        logger.info(
            "FINAL DATAFRAME",
        )

        logger.info(
            "=" * 80,
        )

        logger.info(
            "Rows : %s",
            len(merged),
        )

        logger.info(
            "Columns : %s",
            len(merged.columns),
        )

        logger.info(
            "Column List : %s",
            merged.columns.tolist(),
        )

        logger.info(
            "Has MONTH : %s",
            "MONTH" in merged.columns,
        )

        if "MONTH" in merged.columns:

            logger.info(
                "MONTH Values : %s",
                merged[
                    "MONTH"
                ]
                .drop_duplicates()
                .tolist(),
            )

        logger.info(
            "=" * 80,
        )

        # ======================================================
        # OUTPUT DIRECTORY
        # ======================================================

        dataset_folder = (
            MonthlyMerger.DATASET_FOLDERS.get(
                dataset,
            )
        )

        if dataset_folder is None:

            raise ValueError(
                f"Unknown dataset: {dataset}"
            )

        final_output = (
            output_dir
            / dataset_folder
        )

        final_output.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ======================================================
        # OUTPUT FILE NAME
        # ======================================================

        if dataset == "ANEV":

            filename = (
                f"anev_{month}.parquet"
            )

        elif dataset == "DLPD_PASCABAYAR":

            filename = (
                f"dlpd_pascabayar_{month}.parquet"
            )

        elif dataset == "DLPD_PRABAYAR":

            filename = (
                f"dlpd_prabayar_{month}.parquet"
            )

        elif dataset == "CUSTOMER_LOCATION":

            filename = (
                f"customer_location_{month}.parquet"
            )

        else:

            filename = (
                f"{dataset.lower()}.parquet"
            )

        output_path = (
            final_output
            / filename
        )

        # ------------------------------------------------------
        # Remove obsolete pre-partition DLPD files.
        # ------------------------------------------------------
        #
        # The warehouse reads dlpd_*.parquet. Keeping the old
        # unpartitioned file beside the new monthly partitions would
        # duplicate rows after Warehouse.refresh_tables().
        # ------------------------------------------------------

        if dataset == "DLPD_PASCABAYAR":
            legacy_path = (
                final_output
                / "dlpd_pascabayar.parquet"
            )
            if legacy_path.exists():
                legacy_path.unlink()
                logger.info(
                    "Removed obsolete DLPD legacy parquet: %s",
                    legacy_path,
                )

        elif dataset == "DLPD_PRABAYAR":
            legacy_path = (
                final_output
                / "dlpd_prabayar.parquet"
            )
            if legacy_path.exists():
                legacy_path.unlink()
                logger.info(
                    "Removed obsolete DLPD legacy parquet: %s",
                    legacy_path,
                )

        # ======================================================
        # EXPORT
        # ======================================================

        logger.info(
            "Writing parquet : %s",
            output_path,
        )

        merged.to_parquet(
            output_path,
            index=False,
        )

        logger.info(
            "Parquet exported : %s",
            output_path,
        )

        return output_path