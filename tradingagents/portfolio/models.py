from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_decimal(value: Decimal | int | float | str) -> Decimal:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return decimal_value.normalize()


def _normalize_weight(value: Decimal | int | float | str) -> Decimal:
    decimal_value = _normalize_decimal(value)
    if decimal_value < 0 or decimal_value > 1:
        raise ValueError("weight values must be between 0 and 1")
    return decimal_value


def _normalize_non_negative_decimal(value: Decimal | int | float | str) -> Decimal:
    decimal_value = _normalize_decimal(value)
    if decimal_value < 0:
        raise ValueError("value must be non-negative")
    return decimal_value


class PortfolioMandate(BaseModel):
    starting_cash: Decimal = Field(gt=0)
    risk_profile: Literal["conservative", "balanced", "aggressive"]
    time_horizon_days: int = Field(gt=0)
    max_positions: int = Field(ge=1)
    min_positions: int | None = Field(default=None, ge=1)
    allowed_asset_types: list[Literal["stock", "etf"]] = Field(default_factory=lambda: ["stock", "etf"])
    allow_fractional: bool = False
    allow_short: bool = False
    allow_margin: bool = False
    max_position_weight: Decimal = Decimal("0.20")
    max_sector_weight: Decimal = Decimal("0.35")
    max_turnover_per_rebalance: Decimal = Decimal("0.30")
    min_avg_dollar_volume: Decimal = Decimal("1000000")
    rebalance_cadence: Literal["daily", "weekly"] = "weekly"
    themes: list[str] = Field(default_factory=list)
    watchwords: list[str] = Field(default_factory=list)
    benchmark_symbols: list[str] = Field(default_factory=lambda: ["SPY"])

    @field_validator("starting_cash", "min_avg_dollar_volume", mode="before")
    @classmethod
    def _validate_positive_decimals(cls, value: Decimal | int | float | str) -> Decimal:
        decimal_value = _normalize_decimal(value)
        if decimal_value < 0:
            raise ValueError("value must be non-negative")
        return decimal_value

    @field_validator(
        "max_position_weight",
        "max_sector_weight",
        "max_turnover_per_rebalance",
        mode="before",
    )
    @classmethod
    def _validate_weight_decimals(cls, value: Decimal | int | float | str) -> Decimal:
        return _normalize_weight(value)

    @field_validator("allowed_asset_types")
    @classmethod
    def _validate_asset_types(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("allowed_asset_types must not be empty")
        return sorted(set(value))

    @field_validator("themes", "watchwords", "benchmark_symbols")
    @classmethod
    def _strip_list_values(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item and item.strip()]
        return normalized

    @model_validator(mode="after")
    def _validate_mandate(self) -> "PortfolioMandate":
        if self.allow_short:
            raise ValueError("long-only mandates must set allow_short=False")
        if self.allow_margin:
            raise ValueError("paper portfolio mandates must set allow_margin=False")
        if self.min_positions is not None and self.min_positions > self.max_positions:
            raise ValueError("min_positions cannot exceed max_positions")
        if self.max_position_weight <= 0:
            raise ValueError("max_position_weight must be greater than zero")
        if self.max_sector_weight <= 0:
            raise ValueError("max_sector_weight must be greater than zero")
        if self.max_turnover_per_rebalance < 0:
            raise ValueError("max_turnover_per_rebalance must be non-negative")
        return self


class CandidateIdea(BaseModel):
    symbol: str
    asset_type: Literal["stock", "etf"] = "stock"
    sector: str | None = None
    score: Decimal = Decimal("0")
    confidence: Decimal = Decimal("0")
    thesis_summary: str = ""
    machine_rationale: dict[str, Any] = Field(default_factory=dict)
    avg_dollar_volume: Decimal | None = None
    research_artifact_refs: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("score", "confidence", "avg_dollar_volume", mode="before")
    @classmethod
    def _normalize_optional_decimals(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        decimal_value = _normalize_decimal(value)
        if decimal_value < 0:
            raise ValueError("decimal values must be non-negative")
        return decimal_value


class PositionTarget(BaseModel):
    symbol: str
    target_weight: Decimal
    asset_type: Literal["stock", "etf"] = "stock"
    sector: str | None = None
    thesis_summary: str = ""
    machine_rationale: dict[str, Any] = Field(default_factory=dict)
    price: Decimal | None = None
    avg_dollar_volume: Decimal | None = None

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("target_weight", mode="before")
    @classmethod
    def _validate_target_weight(cls, value: Decimal | int | float | str) -> Decimal:
        return _normalize_non_negative_decimal(value)

    @field_validator("price", "avg_dollar_volume", mode="before")
    @classmethod
    def _validate_optional_positive_decimals(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        decimal_value = _normalize_decimal(value)
        if decimal_value <= 0:
            raise ValueError("value must be greater than zero")
        return decimal_value


class CurrentPosition(BaseModel):
    symbol: str
    quantity: Decimal
    market_value: Decimal
    current_weight: Decimal | None = None
    asset_type: Literal["stock", "etf"] = "stock"
    sector: str | None = None
    price: Decimal | None = None

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("quantity", "market_value", "price", mode="before")
    @classmethod
    def _validate_positive_decimals(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        decimal_value = _normalize_decimal(value)
        if decimal_value < 0:
            raise ValueError("value must be non-negative")
        return decimal_value

    @field_validator("current_weight", mode="before")
    @classmethod
    def _validate_optional_weight(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        return _normalize_weight(value)


class OrderIntent(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    target_weight_before: Decimal
    target_weight_after: Decimal
    quantity_delta: Decimal | None = None
    notional_delta: Decimal
    reason_code: Literal["new_position", "increase", "decrease", "exit"]
    human_reason: str

    @field_validator(
        "target_weight_before",
        "target_weight_after",
        mode="before",
    )
    @classmethod
    def _validate_order_weights(cls, value: Decimal | int | float | str) -> Decimal:
        return _normalize_weight(value)

    @field_validator("quantity_delta", "notional_delta", mode="before")
    @classmethod
    def _validate_order_decimals(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        decimal_value = _normalize_decimal(value)
        if decimal_value < 0:
            raise ValueError("order deltas must be non-negative")
        return decimal_value


class ConstraintCheck(BaseModel):
    name: str
    passed: bool
    details: str


class RebalancePlan(BaseModel):
    as_of: datetime
    current_positions: list[CurrentPosition]
    target_positions: list[PositionTarget]
    orders: list[OrderIntent]
    turnover: Decimal
    constraint_checks: list[ConstraintCheck]
    summary: str

    @field_validator("turnover", mode="before")
    @classmethod
    def _validate_turnover(cls, value: Decimal | int | float | str) -> Decimal:
        return _normalize_weight(value)


class DecisionRecord(BaseModel):
    decision_id: str
    portfolio_id: str
    timestamp: datetime
    inputs_hash: str
    mandate_snapshot: dict[str, Any]
    candidate_set: list[dict[str, Any]]
    target_positions: list[dict[str, Any]]
    rebalance_plan: dict[str, Any]
    human_summary: str
