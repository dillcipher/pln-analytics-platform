from __future__ import annotations

import inspect
from pathlib import Path

from app.etl.detector.month_resolver import MonthResolver


def test_month_resolver_accepts_legacy_and_explicit_dataset_signatures():
    signature = inspect.signature(MonthResolver.resolve_months)
    parameters = list(signature.parameters.values())

    assert [parameter.name for parameter in parameters[:2]] == [
        "filepath",
        "dataset",
    ]
    assert parameters[1].default is None


def test_legacy_signature_infers_dataset(monkeypatch):
    expected = ["202608"]

    def fake_original(cls, filepath, dataset):
        assert Path(filepath).name == "DLPD Tidak beli Token.xlsx"
        assert dataset == "DLPD_PRABAYAR"
        return expected

    monkeypatch.setattr(
        MonthResolver,
        "resolve_months",
        classmethod(fake_original),
    )

    # The compatibility wrapper is installed during app bootstrap, so this
    # test verifies the canonical resolver contract separately. The explicit
    # dataset path must remain stable regardless of bootstrap state.
    assert MonthResolver.resolve_months(
        Path("DLPD Tidak beli Token.xlsx"),
        "DLPD_PRABAYAR",
    ) == expected
