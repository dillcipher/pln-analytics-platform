"""
Synthetic Sample Data Generator
=================================
Generates realistic-shaped (but entirely fictitious) Excel input files
matching all four source schemas, including the multi-file-per-month
ANEV/ANNEV pattern. This exists so the whole pipeline — and the
dashboard on top of it — can be run, demoed, and tested end-to-end
before real PLN exports are wired in. It is NOT part of the production
pipeline; it is a development/demo utility only.

Usage:
    python -m etl.generate_sample_data --output-dir data/raw --months 202606 202607
"""
from __future__ import annotations

import argparse
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from etl.config.schema_registry import (
    DLPD_PASCABAYAR_COLUMNS,
    DLPD_PRABAYAR_COLUMNS,
    PENGECEKAN_COLUMNS,
    SUSPECT_ANEV_COLUMNS,
    SUSPECT_CATEGORIES,
)

RNG = random.Random(42)
NP_RNG = np.random.default_rng(42)

UNITUPI = "UID LAMPUNG"
UNITAP_LIST = ["UP3 TANJUNG KARANG", "UP3 METRO", "UP3 KOTABUMI", "UP3 PRINGSEWU"]
UNITUP_BY_UNITAP = {
    "UP3 TANJUNG KARANG": ["ULP TELUK BETUNG", "ULP KEDATON", "ULP SUKARAME"],
    "UP3 METRO": ["ULP METRO", "ULP SUKADANA", "ULP BATANGHARI"],
    "UP3 KOTABUMI": ["ULP KOTABUMI", "ULP BUKIT KEMUNING", "ULP BLAMBANGAN UMPU"],
    "UP3 PRINGSEWU": ["ULP PRINGSEWU", "ULP GADINGREJO", "ULP TALANGPADANG"],
}
TARIFF_LIST = ["R1", "R1M", "R2", "R3", "B1", "B2", "B3", "I2", "I3"]
FIRST_NAMES = ["Budi", "Siti", "Andi", "Dewi", "Agus", "Rina", "Hendra", "Sri", "Bambang", "Yuni", "Wayan", "Made", "Fitri", "Joko", "Ratna"]
LAST_NAMES = ["Santoso", "Wijaya", "Saputra", "Lestari", "Pratama", "Kurniawan", "Hidayat", "Ramadhan", "Nugroho", "Utami"]

_ALL_PASCA_COLS = set(DLPD_PASCABAYAR_COLUMNS)
_ALL_PRA_COLS = set(DLPD_PRABAYAR_COLUMNS)
_ALL_PENGECEKAN_COLS = set(PENGECEKAN_COLUMNS)


def _fake_name() -> str:
    return f"{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}"


def _fake_idpel(i: int) -> str:
    return f"5117{i:08d}"


def _fake_address() -> str:
    return f"Jl. {RNG.choice(['Merdeka', 'Sudirman', 'Diponegoro', 'Kartini', 'Gajah Mada'])} No. {RNG.randint(1, 200)}"


def _pick_unit() -> tuple[str, str, str]:
    unitap = RNG.choice(UNITAP_LIST)
    unitup = RNG.choice(UNITUP_BY_UNITAP[unitap])
    return UNITUPI, unitap, unitup


def _fill_remaining_columns(df: pd.DataFrame, all_columns: tuple[str, ...]) -> pd.DataFrame:
    """Any schema column not explicitly populated above gets a light,
    type-plausible filler value so the file is schema-complete without
    hand-writing all 80-140 columns individually."""
    n = len(df)
    for col in all_columns:
        if col in df.columns:
            continue
        upper = col.upper()
        if any(tok in upper for tok in ("RP", "KWH", "KVARH", "TEGANGAN", "ARUS", "DAYA", "STAND", "BEBAN", "COS_", "DEVIASI", "FAKTOR", "KVA", "N_", "T_", "C_", "IRT", "KW_")):
            df[col] = np.round(NP_RNG.uniform(0, 5000, size=n), 2)
        elif "TANGGAL" in upper or "TGL" in upper or "WAKTU" in upper:
            df[col] = pd.NaT
        else:
            df[col] = None
    return df[list(all_columns)]


def generate_dlpd_pascabayar(month_key: str, customer_pool: list[str], n: int) -> pd.DataFrame:
    rows = []
    for idpel in RNG.sample(customer_pool, k=min(n, len(customer_pool))):
        _, unitap, unitup = _pick_unit()
        daya = RNG.choice([450, 900, 1300, 2200, 3500, 4400, 5500])
        rows.append(
            {
                "THBLREK": month_key,
                "IDPEL": idpel,
                "NAMA": _fake_name(),
                "ALAMAT": _fake_address(),
                "UNITAP": unitap,
                "UNITUP": unitup,
                "TARIF": RNG.choice(TARIFF_LIST),
                "DAYA": daya,
                "RPTAG": round(NP_RNG.uniform(150_000, 3_000_000), 0),
                "PEMKWH": round(NP_RNG.uniform(50, 900), 1),
                "JAMNYALA": round(NP_RNG.uniform(80, 300), 1),
                "DLPD": RNG.choice([0, 0, 0, 1, 1, 2]),  # skewed toward 0 (normal)
                "DLPD_LM": RNG.choice([0, 0, 1]),
                "DLPD_FKM": RNG.choice([0, 0, 1]),
                "DLPD_KVARH": RNG.choice([0, 0, 1]),
                "DLPD_3BLN": RNG.choice([0, 1]),
            }
        )
    df = pd.DataFrame(rows)
    return _fill_remaining_columns(df, DLPD_PASCABAYAR_COLUMNS)


def generate_dlpd_prabayar(month_key: str, customer_pool: list[str], n: int) -> pd.DataFrame:
    rows = []
    for idpel in RNG.sample(customer_pool, k=min(n, len(customer_pool))):
        unitupi, unitap, unitup = _pick_unit()
        daya = RNG.choice([450, 900, 1300, 2200])
        status = RNG.choice(["SUDAH_DIPERIKSA", "BELUM_DIPERIKSA", "SUDAH_DIPERIKSA"])
        rows.append(
            {
                "IDPEL": idpel,
                "THBL": month_key,
                "UNITUPI": unitupi,
                "UNITAP": unitap,
                "UNITUP": unitup,
                "DAYA": daya,
                "TARIF": RNG.choice(TARIFF_LIST),
                "KRITERIA": RNG.choice(["NORMAL", "SUSPECT", "SUSPECT", "NORMAL"]),
                "NAMA": _fake_name(),
                "ALAMAT": _fake_address(),
                "MEREK_METER": RNG.choice(["ITRON", "STAR", "HEXING", "MECOINDO"]),
                "BELI_TOKEN_AKHIR": (datetime(2026, int(month_key[4:]), 1) - timedelta(days=RNG.randint(0, 60))).strftime("%Y-%m-%d"),
                "JML_P2TL": RNG.choice([0, 0, 0, 1]),
                "DLPD": RNG.choice([0, 0, 0, 1, 1, 2]),
                "STATUS_PERIKSA": status,
            }
        )
    df = pd.DataFrame(rows)
    return _fill_remaining_columns(df, DLPD_PRABAYAR_COLUMNS)


def generate_pengecekan(month_key: str, customer_pool: list[str], n: int) -> pd.DataFrame:
    rows = []
    year, month = int(month_key[:4]), int(month_key[4:])
    for i, idpel in enumerate(RNG.sample(customer_pool, k=min(n, len(customer_pool)))):
        _, unitap, unitup = _pick_unit()
        waktu = datetime(year, month, RNG.randint(1, 27), RNG.randint(7, 16), RNG.randint(0, 59))
        found_anomaly = RNG.random() < 0.35
        rows.append(
            {
                "NO": i + 1,
                "ID_P2TL": f"P2TL-{month_key}-{i+1:05d}",
                "IDPEL": idpel,
                "NAMA": _fake_name(),
                "TARIF": RNG.choice(TARIFF_LIST),
                "DAYA": RNG.choice([450, 900, 1300, 2200]),
                "LATITUDE": round(-5.45 + NP_RNG.uniform(-0.3, 0.3), 6),
                "LONGITUDE": round(105.27 + NP_RNG.uniform(-0.3, 0.3), 6),
                "WAKTU_PERIKSA": waktu,
                "BULAN": month_key,
                "UNIT ULP": unitup,
                "UNIT UP3": unitap,
                "UNIT UID": UNITUPI,
                "DLPD": RNG.choice(["P I", "P II", "P III", "P IV"]) if found_anomaly else "NORMAL",
                "REGU": f"Regu {RNG.randint(1, 6)}",
                "PERUNTUKAN": RNG.choice(["RUMAH TANGGA", "BISNIS", "INDUSTRI"]),
                "STATUS_KWH": RNG.choice(["NORMAL", "RUSAK", "DIGANTI"]),
                "USERNAME": f"petugas{RNG.randint(1,20)}",
                "NAMA_PETUGAS": _fake_name(),
            }
        )
    df = pd.DataFrame(rows)
    return _fill_remaining_columns(df, PENGECEKAN_COLUMNS)


def generate_suspect_period(
    period_start: datetime, period_end: datetime, customer_pool: list[str], n: int
) -> pd.DataFrame:
    rows = []
    days_span = max((period_end - period_start).days, 1)
    for i in range(n):
        idpel = RNG.choice(customer_pool)
        _, unitap, unitup = _pick_unit()
        read_date = period_start + timedelta(days=RNG.randint(0, days_span), hours=RNG.randint(0, 23))
        suspect_name = RNG.choice(SUSPECT_CATEGORIES)
        v_base = RNG.uniform(215, 230)
        rows.append(
            {
                "READ_DATE": read_date,
                "LOCATION_CODE": idpel,
                "LOCATION_NAME": _fake_name(),
                "UNITUPI": UNITUPI,
                "UNITAP": unitap,
                "UNITUP": unitup,
                "TARIFF": RNG.choice(TARIFF_LIST),
                "POWER": RNG.choice([450, 900, 1300, 2200, 3500]),
                "SUSPECT_NAME": suspect_name,
                "VOLTAGE_L1": round(v_base + NP_RNG.uniform(-15, 15), 2),
                "VOLTAGE_L2": round(v_base + NP_RNG.uniform(-15, 15), 2),
                "VOLTAGE_L3": round(v_base + NP_RNG.uniform(-15, 15), 2),
                "VOLTAGE_ANGLE_CONV_L1": round(NP_RNG.uniform(0, 360), 1),
                "VOLTAGE_ANGLE_CONV_L2": round(120 + NP_RNG.uniform(-10, 10), 1),
                "VOLTAGE_ANGLE_CONV_L3": round(240 + NP_RNG.uniform(-10, 10), 1),
                "CURRENT_L1": round(NP_RNG.uniform(0, 25), 2),
                "CURRENT_L2": round(NP_RNG.uniform(0, 25), 2),
                "CURRENT_L3": round(NP_RNG.uniform(0, 25), 2),
                "CURRENT_N": round(NP_RNG.uniform(0, 5), 2),
                "CURRENT_ANGLE_L1": round(NP_RNG.uniform(0, 360), 1),
                "CURRENT_ANGLE_L2": round(NP_RNG.uniform(0, 360), 1),
                "CURRENT_ANGLE_L3": round(NP_RNG.uniform(0, 360), 1),
                "POWER_FACTOR_L1": round(NP_RNG.uniform(0.6, 1.0), 3),
                "POWER_FACTOR_L2": round(NP_RNG.uniform(0.6, 1.0), 3),
                "POWER_FACTOR_L3": round(NP_RNG.uniform(0.6, 1.0), 3),
                "POWER_FACTOR_TOTAL": round(NP_RNG.uniform(0.6, 1.0), 3),
                "ACTIVE_POWER_L1": round(NP_RNG.uniform(0, 5000), 1),
                "ACTIVE_POWER_L2": round(NP_RNG.uniform(0, 5000), 1),
                "ACTIVE_POWER_L3": round(NP_RNG.uniform(0, 5000), 1),
            }
        )
    df = pd.DataFrame(rows)
    return df[list(SUSPECT_ANEV_COLUMNS)]


def _period_slices_for_month(year: int, month: int) -> list[tuple[datetime, datetime, str]]:
    """Mimics the real filename convention: 3 slices per month
    (01-10, 11-20, 21-end), alternating the ANEV/ANNEV spelling exactly
    like the real files do, to prove the reader handles both."""
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    slices = [(1, 10), (11, 20), (21, last_day)]
    prefix = "ANEV" if month <= 2 else "ANNEV"  # mirror the real-world spelling switch
    out = []
    for start_day, end_day in slices:
        start = datetime(year, month, start_day)
        end = datetime(year, month, end_day)
        out.append((start, end, prefix))
    return out


def generate_all(output_dir: Path, months: list[str], customers_per_month: int = 400, suspect_rows_per_period: int = 250) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    customer_pool = [_fake_idpel(i) for i in range(2000)]

    for month_key in months:
        year, month = int(month_key[:4]), int(month_key[4:])

        pasca = generate_dlpd_pascabayar(month_key, customer_pool, customers_per_month)
        pasca.to_excel(output_dir / f"DLPD_Pascabayar_{month_key}.xlsx", sheet_name="main", index=False)

        pra = generate_dlpd_prabayar(month_key, customer_pool, customers_per_month)
        pra.to_excel(output_dir / f"DLPD_Tidak_beli_Token_{month_key}.xlsx", sheet_name="Sheet1", index=False)

        pengecekan = generate_pengecekan(month_key, customer_pool, int(customers_per_month * 0.6))
        pengecekan.to_excel(output_dir / f"Pengecekan_{month_key}.xlsx", sheet_name="DATA", index=False)

        for start, end, prefix in _period_slices_for_month(year, month):
            suspect_df = generate_suspect_period(start, end, customer_pool, suspect_rows_per_period)
            fname = f"17_{prefix}_{start:%Y%m%d}-{end:%Y%m%d}.xlsx"
            suspect_df.to_excel(output_dir / fname, sheet_name="Sheet1", index=False)

        print(f"[generate_sample_data] month={month_key}: wrote Pascabayar, Prabayar, Pengecekan, and 3 ANEV period files")

    print(f"[generate_sample_data] Done. Files written to {output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic PLN-shaped sample data")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--months", nargs="+", default=["202606", "202607"], help="YYYYMM list")
    parser.add_argument("--customers-per-month", type=int, default=400)
    parser.add_argument("--suspect-rows-per-period", type=int, default=250)
    args = parser.parse_args()

    generate_all(args.output_dir, args.months, args.customers_per_month, args.suspect_rows_per_period)


if __name__ == "__main__":
    main()
