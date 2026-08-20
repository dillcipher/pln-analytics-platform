from __future__ import annotations

import logging
from typing import Any, Protocol

from app.infrastructure.duckdb.executive_repository import (
    DuckDbExecutiveRepository,
)

logger = logging.getLogger(__name__)


# ==========================================================
# REPOSITORY CONTRACT
# ==========================================================


class ExecutiveRepositoryLike(Protocol):
    """
    Minimal repository contract required by the Executive use cases.

    The concrete implementation can still be DuckDbExecutiveRepository,
    but the application layer depends on the repository contract rather
    than hard-coding repository behavior into the use case.
    """

    def get_available_months(self) -> list[Any]: ...

    def get_kpis(
        self,
        month_key: str,
    ) -> Any: ...

    def get_chart_data(
        self,
        month_key: str,
    ) -> dict[str, Any]: ...


# ==========================================================
# SHARED HELPERS
# ==========================================================


def _month_key_from_option(value: Any) -> str | None:
    """
    Normalize a repository month option into a month_key string.

    Supports:
        MonthOption-like objects
        dictionaries
        raw strings / numbers
    """

    if value is None:
        return None

    if hasattr(value, "month_key"):
        month_key = getattr(value, "month_key", None)
        return str(month_key) if month_key is not None else None

    if isinstance(value, dict):
        month_key = value.get("month_key")
        if month_key is None:
            return None
        return str(month_key)

    text = str(value).strip()
    return text or None


def _resolve_latest_month(
    repository: ExecutiveRepositoryLike,
    month_key: str | None,
) -> str | None:
    """
    Resolve the requested month.

    Explicit month_key ALWAYS wins.

    This is important for the Executive dropdown:
    selecting 202608 must query 202608 instead of silently
    falling back to the latest available month.
    """

    if month_key:
        return str(month_key).strip() or None

    months = repository.get_available_months()

    if not months:
        return None

    normalized = [
        key
        for key in (
            _month_key_from_option(item)
            for item in months
        )
        if key
    ]

    if not normalized:
        return None

    # Month keys are expected to be YYYYMM, so lexical sorting
    # is deterministic and keeps the latest month at the end.
    normalized.sort()

    return normalized[-1]


def _as_list(value: Any) -> list[Any]:
    """
    Normalize repository output into a list.

    None      -> []
    list      -> unchanged
    tuple     -> list
    dict      -> [dict]
    scalar    -> [scalar]
    iterable  -> list(iterable)
    """

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, dict):
        return [value]

    if isinstance(value, (str, bytes)):
        return [value]

    try:
        return list(value)
    except TypeError:
        return [value]


def _safe_number(value: Any, default: float = 0.0) -> float:
    """
    Convert numeric-like values safely.

    Repository values can occasionally arrive as Decimal,
    numpy scalar, strings, or None.
    """

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if number != number:
        return default

    return number


def _empty_data_science() -> dict[str, Any]:
    return {
        "correlation": [],
        "linear_regression": [],
        "feature_importance": [],
        "pra_pasca_classification": [],
        "priority_by_unitap": [],
        "priority_by_classification": [],
        "inspection_coverage": {
            "total_population": 0,
            "inspected": 0,
            "remaining": 0,
            "normal": 0,
            "findings": 0,
            "coverage_pct": 0.0,
            "finding_rate_pct": 0.0,
        },
        "repeat_intensity": {
            "total_locations": 0,
            "repeat_locations": 0,
            "repeat_occurrences": 0,
            "repeat_rate_pct": 0.0,
            "avg_repeat_occurrences_per_repeat_location": 0.0,
            "max_repeat_count": 0,
        },
        "concentration": {
            "unitap": [],
            "top_unitap": None,
            "top_3_share_pct": 0.0,
        },
    }


def _empty_pra_monthly() -> dict[str, Any]:
    return {
        "total_locations": 0,
        "total_classifications": 0,
        "classification": [],
        "unitap": [],
    }


def _empty_pasca_repeat() -> dict[str, Any]:
    return {
        "total_locations": 0,
        "repeat_locations": 0,
        "repeat_occurrences": 0,
        "repeat_rate_pct": 0.0,
        "frequency": [],
        "classification": [],
    }


# ==========================================================
# EXECUTIVE KPI
# ==========================================================


class GetExecutiveKpis:
    """
    Application use case for Executive KPI.

    The selected month is passed directly to the repository.
    When no month is supplied, the latest available month is used.
    """

    def __init__(
        self,
        repository: ExecutiveRepositoryLike | None = None,
    ) -> None:
        self._repository = (
            repository
            if repository is not None
            else DuckDbExecutiveRepository()
        )

    def execute(
        self,
        month_key: str | None = None,
    ) -> dict[str, Any]:
        resolved_month = _resolve_latest_month(
            self._repository,
            month_key,
        )

        empty_result = {
            "month_key": resolved_month,
            "total_customers": 0,
            "total_suspects": 0,
            "total_normal": 0,
            "total_findings": 0,
            "remaining_inspection": 0,
            "progress_pct": 0.0,
            "hit_rate_pct": 0.0,
        }

        if not resolved_month:
            return empty_result

        result = self._repository.get_kpis(
            resolved_month,
        )

        if result is None:
            return empty_result

        return {
            "month_key": getattr(
                result,
                "month_key",
                resolved_month,
            ),
            "total_customers": int(
                _safe_number(
                    getattr(
                        result,
                        "total_customers",
                        0,
                    ),
                ),
            ),
            "total_suspects": int(
                _safe_number(
                    getattr(
                        result,
                        "total_suspects",
                        0,
                    ),
                ),
            ),
            "total_normal": int(
                _safe_number(
                    getattr(
                        result,
                        "total_normal",
                        0,
                    ),
                ),
            ),
            "total_findings": int(
                _safe_number(
                    getattr(
                        result,
                        "total_findings",
                        0,
                    ),
                ),
            ),
            "remaining_inspection": int(
                _safe_number(
                    getattr(
                        result,
                        "remaining_inspection",
                        0,
                    ),
                ),
            ),
            "progress_pct": round(
                _safe_number(
                    getattr(
                        result,
                        "progress_pct",
                        0,
                    ),
                ),
                2,
            ),
            "hit_rate_pct": round(
                _safe_number(
                    getattr(
                        result,
                        "hit_rate_pct",
                        0,
                    ),
                ),
                2,
            ),
        }


# ==========================================================
# EXECUTIVE MONTHS
# ==========================================================


class GetExecutiveMonths:
    """
    Return all available Executive periods.

    The result is normalized and sorted by month_key so the frontend
    dropdown has deterministic ordering.
    """

    def __init__(
        self,
        repository: ExecutiveRepositoryLike | None = None,
    ) -> None:
        self._repository = (
            repository
            if repository is not None
            else DuckDbExecutiveRepository()
        )

    def execute(self) -> list[Any]:
        months = self._repository.get_available_months()

        if not months:
            return []

        # Preserve the original MonthOption/dict shape because the
        # API response already expects that structure.
        return sorted(
            months,
            key=lambda item: _month_key_from_option(item) or "",
        )


# ==========================================================
# EXECUTIVE UNIT CHART
# ==========================================================


class GetExecutiveUnitChart:
    """
    Compatibility use case for the UNITAP distribution chart.
    """

    def __init__(
        self,
        repository: ExecutiveRepositoryLike | None = None,
    ) -> None:
        self._repository = (
            repository
            if repository is not None
            else DuckDbExecutiveRepository()
        )

    def execute(
        self,
        month_key: str | None = None,
    ) -> list[dict[str, Any]]:
        resolved_month = _resolve_latest_month(
            self._repository,
            month_key,
        )

        if not resolved_month:
            return []

        result = self._repository.get_chart_data(
            resolved_month,
        )

        if not isinstance(result, dict):
            return []

        return _as_list(
            result.get(
                "bar_by_unitap",
            ),
        )

# ==========================================================
# EXECUTIVE TARIFF CHART
# ==========================================================


class GetExecutiveTariffChart:
    """
    Compatibility use case for the tariff distribution chart.
    """

    def __init__(
        self,
        repository: ExecutiveRepositoryLike | None = None,
    ) -> None:
        self._repository = (
            repository
            if repository is not None
            else DuckDbExecutiveRepository()
        )

    def execute(
        self,
        month_key: str | None = None,
    ) -> list[dict[str, Any]]:
        resolved_month = _resolve_latest_month(
            self._repository,
            month_key,
        )

        if not resolved_month:
            return []

        result = self._repository.get_chart_data(
            resolved_month,
        )

        if not isinstance(result, dict):
            return []

        return _as_list(
            result.get(
                "pie_by_tariff",
            ),
        )


# ==========================================================
# EXECUTIVE CHARTS
# ==========================================================


class GetExecutiveCharts:
    """
    Complete Executive Dashboard application use case.

    The repository remains the source of analytical data. This layer:

        1. resolves the selected period,
        2. preserves every existing chart payload,
        3. normalizes optional analytical sections,
        4. derives PRA-vs-PASCA classification exposure when the
           repository does not explicitly provide it,
        5. never invents correlation/regression/model results.

    PRA:
        selected-month exposure.

    PASCA:
        repeat/persistence across historical months up to the
        selected month, as defined by the repository.
    """

    def __init__(
        self,
        repository: ExecutiveRepositoryLike | None = None,
    ) -> None:
        self._repository = (
            repository
            if repository is not None
            else DuckDbExecutiveRepository()
        )

    def execute(
        self,
        month_key: str | None = None,
    ) -> dict[str, Any]:
        resolved_month = _resolve_latest_month(
            self._repository,
            month_key,
        )

        if not resolved_month:
            return self._empty_result()

        result = self._repository.get_chart_data(
            resolved_month,
        )

        if not isinstance(result, dict):
            logger.warning(
                "Executive chart repository returned "
                "non-dict payload for month %s.",
                resolved_month,
            )
            return self._empty_result()

        pra_monthly = self._normalize_pra_monthly(
            result.get("pra_monthly"),
        )

        pasca_repeat = self._normalize_pasca_repeat(
            result.get("pasca_repeat"),
        )

        # ------------------------------------------------------
        # Data Science
        # ------------------------------------------------------
        #
        # Prefer a Data Science payload already calculated by the
        # repository. This prevents the use case from performing
        # statistical calculations twice.
        #
        # If the repository does not expose one, only the
        # descriptive PRA/PASCA classification comparison is derived
        # here. Correlation, regression and feature importance are
        # NOT fabricated from aggregate counts.
        # ------------------------------------------------------

        data_science = self._get_data_science(
            result=result,
            month_key=resolved_month,
            pra_monthly=pra_monthly,
            pasca_repeat=pasca_repeat,
        )

        return {
            # ==================================================
            # EXISTING EXECUTIVE CHARTS
            # ==================================================

            "bar_by_unitap": _as_list(
                result.get("bar_by_unitap"),
            ),

            "pie_by_tariff": _as_list(
                result.get("pie_by_tariff"),
            ),

            "donut_by_segment": _as_list(
                result.get("donut_by_segment"),
            ),

            "monthly_trend": _as_list(
                result.get("monthly_trend"),
            ),

            "ranking_by_ulp": _as_list(
                result.get("ranking_by_ulp"),
            ),

            "heatmap_unitap_x_category": _as_list(
                result.get(
                    "heatmap_unitap_x_category",
                ),
            ),

            # ==================================================
            # ANEV / EDA
            # ==================================================

            "anev_classification": _as_list(
                result.get("anev_classification"),
            ),

            "anev_by_unitap": _as_list(
                result.get("anev_by_unitap"),
            ),

            "anev_by_tariff": _as_list(
                result.get("anev_by_tariff"),
            ),

            # ==================================================
            # PRA
            # ==================================================

            "pra_monthly": pra_monthly,

            # ==================================================
            # PASCA
            # ==================================================

            "pasca_repeat": pasca_repeat,

            # ==================================================
            # DATA SCIENCE
            # ==================================================

            "data_science": data_science,

            # ==================================================
            # COMPATIBILITY
            # ==================================================

            "repeat_cases": _as_list(
                result.get("repeat_cases"),
            ),
        }

    # ==========================================================
    # PRA NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_pra_monthly(
        value: Any,
    ) -> dict[str, Any]:
        """
        Normalize PRA monthly analytics.

        The repository may return a complete dictionary or nothing.
        """

        if not isinstance(value, dict):
            return _empty_pra_monthly()

        return {
            "total_locations": int(
                _safe_number(
                    value.get("total_locations"),
                ),
            ),
            "total_classifications": int(
                _safe_number(
                    value.get("total_classifications"),
                ),
            ),
            "classification": _as_list(
                value.get("classification"),
            ),
            "unitap": _as_list(
                value.get("unitap"),
            ),
        }

    # ==========================================================
    # PASCA NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_pasca_repeat(
        value: Any,
    ) -> dict[str, Any]:
        """
        Normalize PASCA persistence analytics.
        """

        if not isinstance(value, dict):
            return _empty_pasca_repeat()

        frequency = []

        for item in _as_list(
            value.get("frequency"),
        ):
            if not isinstance(item, dict):
                continue

            frequency.append(
                {
                    "repeat_count": int(
                        _safe_number(
                            item.get("repeat_count"),
                        ),
                    ),
                    "locations": int(
                        _safe_number(
                            item.get("locations"),
                        ),
                    ),
                }
            )

        classification = []

        for item in _as_list(
            value.get("classification"),
        ):
            if not isinstance(item, dict):
                continue

            classification.append(
                {
                    "classification": str(
                        item.get(
                            "classification",
                            "",
                        ),
                    ),
                    "total_locations": int(
                        _safe_number(
                            item.get(
                                "total_locations",
                            ),
                        ),
                    ),
                    "repeat_locations": int(
                        _safe_number(
                            item.get(
                                "repeat_locations",
                            ),
                        ),
                    ),
                    "repeat_occurrences": int(
                        _safe_number(
                            item.get(
                                "repeat_occurrences",
                            ),
                        ),
                    ),
                }
            )

        repeat_locations = int(
            _safe_number(
                value.get("repeat_locations"),
            ),
        )

        total_locations = int(
            _safe_number(
                value.get("total_locations"),
            ),
        )

        repeat_rate = _safe_number(
            value.get("repeat_rate_pct"),
        )

        # If repository omitted the percentage but supplied both
        # numerator and denominator, calculate it here.
        if (
            repeat_rate == 0.0
            and total_locations > 0
            and repeat_locations > 0
        ):
            repeat_rate = (
                repeat_locations
                / total_locations
                * 100.0
            )

        return {
            "total_locations": total_locations,
            "repeat_locations": repeat_locations,
            "repeat_occurrences": int(
                _safe_number(
                    value.get("repeat_occurrences"),
                ),
            ),
            "repeat_rate_pct": round(
                repeat_rate,
                2,
            ),
            "frequency": frequency,
            "classification": classification,
        }

    # ==========================================================
    # DATA SCIENCE
    # ==========================================================

    def _get_data_science(
        self,
        *,
        result: dict[str, Any],
        month_key: str,
        pra_monthly: dict[str, Any],
        pasca_repeat: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Resolve the complete analytical payload.

        Priority:

        1. `data_science` already returned by get_chart_data().
        2. Optional repository-level `get_data_science(month_key)`.
        3. Optional individual statistical repository methods.
        4. PRA-vs-PASCA classification exposure is derived when absent.

        The repository is the source of analytical calculations. This
        use case only normalizes and preserves them.

        Correlation, regression, and feature-importance results are never
        fabricated from aggregate counts.
        """

        def normalize(payload: Any) -> dict[str, Any]:
            if not isinstance(payload, dict):
                payload = {}

            normalized = _empty_data_science()

            normalized["correlation"] = _as_list(
                payload.get("correlation"),
            )
            normalized["linear_regression"] = _as_list(
                payload.get("linear_regression"),
            )
            normalized["feature_importance"] = _as_list(
                payload.get("feature_importance"),
            )
            normalized["pra_pasca_classification"] = _as_list(
                payload.get("pra_pasca_classification"),
            )

            # These five fields are descriptive analytical evidence already
            # calculated by DuckDbExecutiveRepository.
            normalized["priority_by_unitap"] = _as_list(
                payload.get("priority_by_unitap"),
            )
            normalized["priority_by_classification"] = _as_list(
                payload.get("priority_by_classification"),
            )

            inspection = payload.get("inspection_coverage")
            if isinstance(inspection, dict):
                normalized["inspection_coverage"] = {
                    "total_population": int(
                        _safe_number(inspection.get("total_population")),
                    ),
                    "inspected": int(
                        _safe_number(inspection.get("inspected")),
                    ),
                    "remaining": int(
                        _safe_number(inspection.get("remaining")),
                    ),
                    "normal": int(
                        _safe_number(inspection.get("normal")),
                    ),
                    "findings": int(
                        _safe_number(inspection.get("findings")),
                    ),
                    "coverage_pct": round(
                        _safe_number(inspection.get("coverage_pct")),
                        2,
                    ),
                    "finding_rate_pct": round(
                        _safe_number(inspection.get("finding_rate_pct")),
                        2,
                    ),
                }

            repeat_intensity = payload.get("repeat_intensity")
            if isinstance(repeat_intensity, dict):
                normalized["repeat_intensity"] = {
                    "total_locations": int(
                        _safe_number(repeat_intensity.get("total_locations")),
                    ),
                    "repeat_locations": int(
                        _safe_number(repeat_intensity.get("repeat_locations")),
                    ),
                    "repeat_occurrences": int(
                        _safe_number(repeat_intensity.get("repeat_occurrences")),
                    ),
                    "repeat_rate_pct": round(
                        _safe_number(repeat_intensity.get("repeat_rate_pct")),
                        2,
                    ),
                    "avg_repeat_occurrences_per_repeat_location": round(
                        _safe_number(
                            repeat_intensity.get(
                                "avg_repeat_occurrences_per_repeat_location",
                            ),
                        ),
                        2,
                    ),
                    "max_repeat_count": int(
                        _safe_number(repeat_intensity.get("max_repeat_count")),
                    ),
                }

            concentration = payload.get("concentration")
            if isinstance(concentration, dict):
                concentration_rows = []

                for item in _as_list(
                    concentration.get("unitap"),
                ):
                    if not isinstance(item, dict):
                        continue

                    concentration_rows.append(
                        {
                            "unitap": str(item.get("unitap", "")),
                            "locations": int(
                                _safe_number(item.get("locations")),
                            ),
                            "share_pct": round(
                                _safe_number(item.get("share_pct")),
                                2,
                            ),
                        }
                    )

                top_unitap = concentration.get("top_unitap")
                if isinstance(top_unitap, dict):
                    top_unitap = {
                        "unitap": str(top_unitap.get("unitap", "")),
                        "locations": int(
                            _safe_number(top_unitap.get("locations")),
                        ),
                        "share_pct": round(
                            _safe_number(top_unitap.get("share_pct")),
                            2,
                        ),
                    }
                else:
                    top_unitap = None

                normalized["concentration"] = {
                    "unitap": concentration_rows,
                    "top_unitap": top_unitap,
                    "top_3_share_pct": round(
                        _safe_number(
                            concentration.get("top_3_share_pct"),
                        ),
                        2,
                    ),
                }

            if not normalized["pra_pasca_classification"]:
                normalized[
                    "pra_pasca_classification"
                ] = self._build_pra_pasca_classification(
                    pra_monthly=pra_monthly,
                    pasca_repeat=pasca_repeat,
                )

            return normalized

        # ------------------------------------------------------
        # 1. Repository chart payload.
        # ------------------------------------------------------

        existing = result.get("data_science")
        if isinstance(existing, dict):
            return normalize(existing)

        # ------------------------------------------------------
        # 2. Optional explicit repository method.
        # ------------------------------------------------------

        aggregate_getter = getattr(
            self._repository,
            "get_data_science",
            None,
        )

        if callable(aggregate_getter):
            try:
                statistical_result = aggregate_getter(
                    month_key,
                )
            except Exception:
                logger.exception(
                    "Failed to calculate Executive analytical payload "
                    "for month %s.",
                    month_key,
                )
                statistical_result = None

            if isinstance(statistical_result, dict):
                return normalize(statistical_result)

        # ------------------------------------------------------
        # 3. Compatibility with repositories that expose individual
        # statistical methods.
        # ------------------------------------------------------

        correlation = self._call_repository_method(
            (
                "get_correlation",
                "get_correlation_analysis",
            ),
            month_key,
        )

        regression = self._call_repository_method(
            (
                "get_linear_regression",
                "get_regression_analysis",
            ),
            month_key,
        )

        importance = self._call_repository_method(
            (
                "get_feature_importance",
                "get_feature_importances",
            ),
            month_key,
        )

        pra_pasca = self._call_repository_method(
            (
                "get_pra_pasca_suspect",
                "get_pra_pasca_classification",
                "get_pra_vs_pasca_classification",
            ),
            month_key,
        )

        return normalize(
            {
                "correlation": correlation,
                "linear_regression": regression,
                "feature_importance": importance,
                "pra_pasca_classification": pra_pasca,
            }
        )


    # ==========================================================
    # PRA VS PASCA DESCRIPTIVE ANALYSIS
    # ==========================================================

    @staticmethod
    def _build_pra_pasca_classification(
        *,
        pra_monthly: dict[str, Any],
        pasca_repeat: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Build a comparable PRA vs PASCA classification dataset.

        PRA:
            classification total for the selected month.

        PASCA:
            total PASCA locations carrying the classification in the
            persistence window.

        Important:
            `total_locations` is used for PASCA exposure.
            `repeat_locations` is NOT used as the PASCA total because
            repeat_locations represents persistence, not total exposure.
        """

        pra_items = _as_list(
            pra_monthly.get("classification"),
        )

        pasca_items = _as_list(
            pasca_repeat.get("classification"),
        )

        pra_by_class: dict[str, int] = {}
        pasca_by_class: dict[str, int] = {}

        canonical_names: dict[str, str] = {}

        for item in pra_items:
            if not isinstance(item, dict):
                continue

            raw_name = str(
                item.get(
                    "classification",
                    "",
                ),
            ).strip()

            if not raw_name:
                continue

            key = _canonical_classification(
                raw_name,
            )

            canonical_names.setdefault(
                key,
                raw_name,
            )

            pra_by_class[key] = (
                pra_by_class.get(key, 0)
                + int(
                    _safe_number(
                        item.get("total"),
                    ),
                )
            )

        for item in pasca_items:
            if not isinstance(item, dict):
                continue

            raw_name = str(
                item.get(
                    "classification",
                    "",
                ),
            ).strip()

            if not raw_name:
                continue

            key = _canonical_classification(
                raw_name,
            )

            canonical_names.setdefault(
                key,
                raw_name,
            )

            pasca_by_class[key] = (
                pasca_by_class.get(key, 0)
                + int(
                    _safe_number(
                        item.get(
                            "total_locations",
                        ),
                    ),
                )
            )

        keys = sorted(
            set(pra_by_class)
            | set(pasca_by_class),
            key=lambda key: (
                -(
                    pra_by_class.get(key, 0)
                    + pasca_by_class.get(key, 0)
                ),
                key,
            ),
        )

        result: list[dict[str, Any]] = []

        for key in keys:
            label = canonical_names.get(
                key,
                key,
            )

            result.append(
                {
                    "customer_type": "PRA",
                    "classification": label,
                    "total": pra_by_class.get(
                        key,
                        0,
                    ),
                }
            )

            result.append(
                {
                    "customer_type": "PASCA",
                    "classification": label,
                    "total": pasca_by_class.get(
                        key,
                        0,
                    ),
                }
            )

        return result

    # ==========================================================
    # OPTIONAL REPOSITORY METHOD
    # ==========================================================

    def _call_repository_method(
        self,
        method_names: tuple[str, ...],
        month_key: str,
    ) -> list[Any]:
        """
        Call the first available repository method.

        Preferred:
            method(month_key)

        Compatibility:
            method()

        Missing methods simply mean that the corresponding
        statistical section is unavailable. No fake result is created.
        """

        for method_name in method_names:
            method = getattr(
                self._repository,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                value = method(
                    month_key,
                )
            except TypeError:
                try:
                    value = method()
                except Exception:
                    logger.exception(
                        "Repository method %s failed.",
                        method_name,
                    )
                    continue
            except Exception:
                logger.exception(
                    "Repository method %s failed for month %s.",
                    method_name,
                    month_key,
                )
                continue

            return _as_list(value)

        return []

    # ==========================================================
    # EMPTY RESULT
    # ==========================================================

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "bar_by_unitap": [],
            "pie_by_tariff": [],
            "donut_by_segment": [],
            "monthly_trend": [],
            "ranking_by_ulp": [],
            "heatmap_unitap_x_category": [],

            "anev_classification": [],
            "anev_by_unitap": [],
            "anev_by_tariff": [],

            "pra_monthly": _empty_pra_monthly(),

            "pasca_repeat": _empty_pasca_repeat(),

            "data_science": _empty_data_science(),

            "repeat_cases": [],
        }


# ==========================================================
# CLASSIFICATION NORMALIZATION
# ==========================================================


def _canonical_classification(
    value: str,
) -> str:
    """
    Normalize superficial spelling/spacing differences so PRA and
    PASCA classifications can be compared correctly.

    Examples:

        "ASYMMETRICPOWER BY INSTANT"
        "ASYMMETRIC POWER BY INSTANT"

    become the same comparison key.
    """

    text = " ".join(
        str(value)
        .strip()
        .upper()
        .split(),
    )

    # Remove spaces around punctuation.
    text = text.replace(
        " - ",
        "-",
    )

    # Known source inconsistencies observed in Executive payloads.
    replacements = {
        "ASYMMETRICPOWER": "ASYMMETRIC POWER",
        "INCORRECTPHASE": "INCORRECT PHASE",
        "OVERCURRENT": "OVER CURRENT",
        "VOLTAGE DIP- INSTANT": "VOLTAGE DIP - INSTANT",
        "REVERSAL BYINSTANT": "REVERSAL BY INSTANT",
    }

    for source, target in replacements.items():
        text = text.replace(
            source,
            target,
        )

    return text
