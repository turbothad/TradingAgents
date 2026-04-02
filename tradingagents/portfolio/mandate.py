from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from .models import PortfolioMandate


PROFILE_DEFAULTS = {
    "conservative": {
        "max_position_weight": Decimal("0.12"),
        "max_sector_weight": Decimal("0.25"),
        "max_turnover_per_rebalance": Decimal("0.15"),
        "rebalance_cadence": "weekly",
        "allow_fractional": True,
        "benchmark_symbols": ["SPY", "AGG"],
    },
    "balanced": {
        "max_position_weight": Decimal("0.20"),
        "max_sector_weight": Decimal("0.35"),
        "max_turnover_per_rebalance": Decimal("0.25"),
        "rebalance_cadence": "weekly",
        "allow_fractional": True,
        "benchmark_symbols": ["SPY"],
    },
    "aggressive": {
        "max_position_weight": Decimal("0.25"),
        "max_sector_weight": Decimal("0.45"),
        "max_turnover_per_rebalance": Decimal("0.40"),
        "rebalance_cadence": "daily",
        "allow_fractional": True,
        "benchmark_symbols": ["SPY", "QQQ"],
    },
}


def get_profile_defaults(risk_profile: str) -> dict:
    if risk_profile not in PROFILE_DEFAULTS:
        raise ValueError(f"Unsupported risk profile: {risk_profile}")
    return deepcopy(PROFILE_DEFAULTS[risk_profile])


def create_mandate(**overrides) -> PortfolioMandate:
    risk_profile = overrides.get("risk_profile", "balanced")
    mandate_data = get_profile_defaults(risk_profile)
    mandate_data.update(overrides)
    return PortfolioMandate(**mandate_data)
