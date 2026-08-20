"""
Schema Registry
================
Single source of truth for the expected columns of every raw Excel source
the ETL pipeline consumes. Validation, dtype casting, and column
standardization all read from this registry instead of hardcoding column
lists inline — if PLN adds/renames a column upstream, this is the only
file that needs to change.

Each entry maps a `SourceType` to:
    - required_columns: columns that MUST be present (validation fails
      the file otherwise)
    - dtype_map: pandas dtype coercion applied after reading
    - date_columns: columns parsed as dates
    - primary_key: columns that uniquely identify a record (used for
      dedup when merging multi-file months)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    DLPD_PASCABAYAR = "dlpd_pascabayar"
    DLPD_PRABAYAR = "dlpd_prabayar"
    PENGECEKAN = "pengecekan"
    SUSPECT_ANEV = "suspect_anev"


@dataclass(frozen=True)
class SourceSchema:
    source_type: SourceType
    sheet_name: str
    required_columns: tuple[str, ...]
    date_columns: tuple[str, ...] = field(default_factory=tuple)
    numeric_columns: tuple[str, ...] = field(default_factory=tuple)
    primary_key: tuple[str, ...] = field(default_factory=tuple)


DLPD_PASCABAYAR_COLUMNS: tuple[str, ...] = (
    "THBLREK", "IDPEL", "NAMA", "ALAMAT", "NOBANG", "KETNOBANG", "RT",
    "NODLMRT", "KETNODLMRT", "RW", "KODEPOS", "KDGARDU", "NAMAGARDU",
    "KDDK", "UNITAP", "UNITUP", "TARIF", "KDPT", "KDPT_2", "DAYA",
    "KDPROSESKLP", "POSTINGBILLING", "MSG", "RPPTL", "RPTB", "RPPPN",
    "RPBPJU", "RPBPTRAFO", "RPSEWATRAFO", "RPSEWAKAP", "RPANGSA",
    "RPANGSB", "RPANGSC", "RPMAT", "RPPLN", "RPTAG", "RPBK1", "RPBK2",
    "RPBK3", "RPLWBP", "RPWBP", "RPBLOK3", "RPKVARH", "KWHLWBP",
    "KWHWBP", "BLOK3", "SLALWBP", "SAHLWBP_CABUT", "SLALWBP_PASANG",
    "SAHLWBP", "SLAWBP", "SAHWBP_CABUT", "SLAWBP_PASANG", "SAHWBP",
    "SLAKVARH", "SAHKVARH_CABUT", "SLAKVARH_PASANG", "SAHKVARH",
    "SAHLWBP_EXP", "SAHWBP_EXP", "SAHKVARH_EXP", "SAHLWBP_CABUT_EXP",
    "SLALWBP_PASANG_EXP", "SAHWBP_CABUT_EXP", "SLAWBP_PASANG_EXP",
    "SAHKVARH_CABUT_EXP", "SLAKVARH_PASANG_EXP", "PEMKWH", "JAMNYALA",
    "PEMKVARH", "KELBKVARH", "DAYAMAKS", "DAYAMAX_WBP", "PEMDA",
    "KOGOL", "SUBKOGOL", "FAKM", "FAKMKVARH", "TGLCABUTPASANG", "DLPD",
    "DLPD_LM", "DLPD_FKM", "DLPD_KVARH", "DLPD_3BLN", "DLPD_JNSMUTASI",
    "DLPD_TGLBACA", "ALASAN_KOREKSI", "JAMNYALA600", "JAMNYALA400", "89",
)

DLPD_PRABAYAR_COLUMNS: tuple[str, ...] = (
    "IDPEL", "THBL", "UNITUP", "NOMOR_METER", "UNITUPI", "UNITAP",
    "DAYA", "TARIF", "KRITERIA", "NAMA", "ALAMAT", "KODE_GARDU",
    "NO_TIANG", "KDDK", "KOORDINAT_X", "KOORDINAT_Y", "MEREK_METER",
    "THN_BUAT_METER", "KRN", "TGLPASANG_KWH", "JENIS_MK", "JML_P2TL",
    "BELI_TOKEN_AKHIR", "USER_PETUGAS_CT", "NAMA_PETUGAS_CT", "JML_CT",
    "DLPD", "KETERANGAN", "STATUS_PERIKSA",
)

PENGECEKAN_COLUMNS: tuple[str, ...] = (
    "NO", "ID_P2TL", "IDPEL", "NAMA", "TARIF", "DAYA", "GARDU", "TIANG",
    "LATITUDE", "LONGITUDE", "SESUAI_MERK", "MERK_METER", "STAND_LWBP",
    "STAND_WBP", "STAND_KVARH", "KODE_PESAN", "UPDATE_STATUS",
    "PERUNTUKAN", "CATATAN", "PEMUTUSAN", "KWH_TS", "WAKTU_PERIKSA",
    "REGU", "SUMBER", "DLPD", "SUB_DLPD", "MATERIAL_KWH", "JENISLAYANAN",
    "JENISPENGUKURAN", "NOMOR_METER", "TEGANGAN_METER", "ARUS_METER",
    "KONSTANTA_METER", "WAKTU_METER", "MATERIAL_MCB", "MATERIAL_BOX",
    "TEGANGAN_R_N", "TEGANGAN_S_N", "TEGANGAN_T_N", "TEGANGAN_R_S",
    "TEGANGAN_S_T", "TEGANGAN_T_R", "BEBAN_PRIMER_R", "BEBAN_PRIMER_S",
    "BEBAN_PRIMER_T", "BEBAN_SEKUNDER_R", "BEBAN_SEKUNDER_S",
    "BEBAN_SEKUNDER_T", "COS_BEBAN_R", "COS_BEBAN_S", "BULAN", "DEVIASI",
    "ARUS_CT_PRIMER_R", "ARUS_CT_PRIMER_S", "ARUS_CT_PRIMER_T",
    "ARUS_CT_SEKUNDER_R", "ARUS_CT_SEKUNDER_S", "ARUS_CT_SEKUNDER_T",
    "RUPIAH_TS", "RUPIAH_KWH", "UNIT ULP", "STATUS_KWH", "NOMOR_BA",
    "MATERIAL_CTPT", "GANTI_MATERIAL", "DURASI_PERIKSA",
    "TRAFO_ARUS_KWH", "TRAFO_TEGANGAN_KWH", "FAKTOR_KALI_KWH", "FX_KWH",
    "FX_KVARH", "FX_PRIMER", "FX_SEKUNDER", "KVA", "N_KWH", "N_KVARH",
    "T_KWH", "T_KVARH", "C_KWH", "C_KVARH", "IRT_PRIMER", "IRT_SEKUNDER",
    "COS_IRT", "KWH_P1", "KVARH_P1", "KW_PRIMER", "FAKTOR_KALI_KWH_R",
    "DEVIASI_CT_R", "DEVIASI_CT_S", "DEVIASI_CT_T", "IRT_PRIMER_CT",
    "IRT_SEKUNDER_CT", "FAKTOR_KALI_KWH_IRT", "DEVIASI_CT",
    "UNIT UP3", "UNIT UID", "NIK_PELANGGAN", "MSISDN_PELANGGAN",
    "TS_AP2T", "NO_AGENDA", "TANGGAL_SPH", "TINDAKLANJUT_PEMERIKSAAN",
    "USERNAME", "NAMA_PETUGAS", "CEK",
)

# The Suspect Analytics module (ANEV files) is described by the platform
# brief's Detail Page column list. This is the canonical instant-reading
# / P2TL analytics export.
SUSPECT_ANEV_COLUMNS: tuple[str, ...] = (
    "READ_DATE", "LOCATION_CODE", "LOCATION_NAME", "UNITUPI", "UNITAP",
    "UNITUP", "TARIFF", "POWER", "SUSPECT_NAME",
    "VOLTAGE_L1", "VOLTAGE_L2", "VOLTAGE_L3",
    "VOLTAGE_ANGLE_CONV_L1", "VOLTAGE_ANGLE_CONV_L2", "VOLTAGE_ANGLE_CONV_L3",
    "CURRENT_L1", "CURRENT_L2", "CURRENT_L3", "CURRENT_N",
    "CURRENT_ANGLE_L1", "CURRENT_ANGLE_L2", "CURRENT_ANGLE_L3",
    "POWER_FACTOR_L1", "POWER_FACTOR_L2", "POWER_FACTOR_L3", "POWER_FACTOR_TOTAL",
    "ACTIVE_POWER_L1", "ACTIVE_POWER_L2", "ACTIVE_POWER_L3",
)

# The nine anomaly categories that appear as SUSPECT_NAME values, and
# become the pivoted columns of the Suspect Summary page.
SUSPECT_CATEGORIES: tuple[str, ...] = (
    "ASYMMETRIC POWER BY INSTANT",
    "INCORRECT PHASE BY INSTANT",
    "OVER CURRENT BY INSTANT",
    "OVER VOLTAGE BY INSTANT",
    "REVERSAL BY INSTANT",
    "TIME DIFFERENCE - INSTANT",
    "UNBALANCE CURRENT BY INSTANT",
    "UNDER VOLTAGE BY INSTANT",
    "VOLTAGE DIP - INSTANT",
)

SCHEMA_REGISTRY: dict[SourceType, SourceSchema] = {
    SourceType.DLPD_PASCABAYAR: SourceSchema(
        source_type=SourceType.DLPD_PASCABAYAR,
        sheet_name="main",
        required_columns=DLPD_PASCABAYAR_COLUMNS,
        date_columns=("TGLCABUTPASANG", "DLPD_TGLBACA"),
        numeric_columns=("RPTAG", "PEMKWH", "DAYA", "DLPD"),
        primary_key=("IDPEL", "THBLREK"),
    ),
    SourceType.DLPD_PRABAYAR: SourceSchema(
        source_type=SourceType.DLPD_PRABAYAR,
        sheet_name="Sheet1",
        required_columns=DLPD_PRABAYAR_COLUMNS,
        date_columns=("TGLPASANG_KWH",),
        numeric_columns=("DAYA", "JML_P2TL", "JML_CT", "DLPD"),
        primary_key=("IDPEL", "THBL"),
    ),
    SourceType.PENGECEKAN: SourceSchema(
        source_type=SourceType.PENGECEKAN,
        sheet_name="DATA",
        required_columns=PENGECEKAN_COLUMNS,
        date_columns=("WAKTU_PERIKSA", "TANGGAL_SPH"),
        numeric_columns=("DAYA", "RUPIAH_TS", "RUPIAH_KWH", "KWH_TS"),
        primary_key=("ID_P2TL",),
    ),
    SourceType.SUSPECT_ANEV: SourceSchema(
        source_type=SourceType.SUSPECT_ANEV,
        sheet_name="Sheet1",
        required_columns=SUSPECT_ANEV_COLUMNS,
        date_columns=("READ_DATE",),
        numeric_columns=(
            "VOLTAGE_L1", "VOLTAGE_L2", "VOLTAGE_L3", "CURRENT_L1",
            "CURRENT_L2", "CURRENT_L3", "CURRENT_N", "POWER_FACTOR_TOTAL",
            "ACTIVE_POWER_L1", "ACTIVE_POWER_L2", "ACTIVE_POWER_L3", "POWER",
        ),
        primary_key=("LOCATION_CODE", "READ_DATE", "SUSPECT_NAME"),
    ),
}
