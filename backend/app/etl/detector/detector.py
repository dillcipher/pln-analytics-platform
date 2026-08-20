from __future__ import annotations

from pathlib import Path


class FileDetector:
    """
    Detect dataset type from uploaded filename.

    Supported datasets:

    - ANEV
    - DLPD_PASCABAYAR
    - DLPD_PRABAYAR
    - PENGECEKAN
    - CUSTOMER_LOCATION

    CUSTOMER_LOCATION sources:

    - DIL_SALDO_MASK_*.xlsx
    - TO_PRABAYAR.xlsx
    - TO_PASCABAYAR.xlsx

    TO_PRABAYAR and TO_PASCABAYAR are fixed coordinate masters.
    They must never be classified as DLPD files.
    """

    ANEV = "ANEV"
    DLPD_PASCABAYAR = "DLPD_PASCABAYAR"
    DLPD_PRABAYAR = "DLPD_PRABAYAR"
    PENGECEKAN = "PENGECEKAN"
    CUSTOMER_LOCATION = "CUSTOMER_LOCATION"
    UNKNOWN = "UNKNOWN"

    COORDINATE_MASTER_FILENAMES = {
        "to_prabayar.xlsx",
        "to_pascabayar.xlsx",
    }

    @staticmethod
    def _normalize_filename(filepath: Path) -> str:
        """
        Normalize filename for reliable detection.

        Examples:
            TO_PRABAYAR.xlsx
            TO-PRABAYAR.xlsx
            TO PRABAYAR.xlsx

        All normalize to:
            to_prabayar.xlsx
        """

        name = Path(filepath).name.lower().strip()

        name = name.replace(
            "-",
            "_",
        )

        name = name.replace(
            " ",
            "_",
        )

        while "__" in name:
            name = name.replace(
                "__",
                "_",
            )

        return name

    @classmethod
    def is_coordinate_master(
        cls,
        filepath: Path,
    ) -> bool:
        """
        Return True only for the two fixed TO coordinate masters.
        """

        return (
            cls._normalize_filename(filepath)
            in cls.COORDINATE_MASTER_FILENAMES
        )

    @classmethod
    def detect(
        cls,
        filepath: Path,
    ) -> str:
        """
        Detect the dataset represented by a file.

        Detection order is intentional:

            1. Exact coordinate masters
            2. DIL/customer location
            3. DLPD pascabayar
            4. DLPD prabayar
            5. PENGECEKAN
            6. ANEV
            7. UNKNOWN

        Exact TO matching happens first so a future filename such as
        "DLPD_TO_PRABAYAR.xlsx" cannot accidentally bypass the
        coordinate-master rule.
        """

        name = cls._normalize_filename(
            filepath,
        )

        # ======================================================
        # FIXED TO COORDINATE MASTERS
        # ======================================================

        if cls.is_coordinate_master(filepath):
            return cls.CUSTOMER_LOCATION

        # ======================================================
        # DIL / CUSTOMER LOCATION
        # ======================================================

        if (
            "dil_saldo_mask" in name
            or "dil_saldo" in name
        ):
            return cls.CUSTOMER_LOCATION

        # ======================================================
        # DLPD PASCABAYAR
        # ======================================================

        if (
            "dlpd" in name
            and (
                "pascabayar" in name
                or "pasca_bayar" in name
                or (
                    "pln" in name
                    and "prabayar" not in name
                )
            )
        ):
            return cls.DLPD_PASCABAYAR

        # ======================================================
        # DLPD PRABAYAR
        # ======================================================

        if (
            "dlpd" in name
            and (
                "tidak_beli_token" in name
                or "prabayar" in name
                or "pra_bayar" in name
            )
        ):
            return cls.DLPD_PRABAYAR

        # ======================================================
        # PENGECEKAN
        # ======================================================

        if "pengecekan" in name:
            return cls.PENGECEKAN

        # ======================================================
        # ANEV
        # ======================================================

        if (
            "anev" in name
            or "17_anev" in name
        ):
            return cls.ANEV

        return cls.UNKNOWN