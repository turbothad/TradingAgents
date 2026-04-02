from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from tradingagents.portfolio.models import OrderIntent, PortfolioMandate


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class BrokerAccount(BaseModel):
    account_id: str
    cash: Decimal
    buying_power: Decimal
    equity: Decimal
    currency: str = "USD"
    is_paper: bool = True
    trading_blocked: bool = False

    @field_validator("cash", "buying_power", "equity", mode="before")
    @classmethod
    def _validate_decimals(cls, value: Decimal | int | float | str) -> Decimal:
        decimal_value = _to_decimal(value)
        if decimal_value < 0:
            raise ValueError("account values must be non-negative")
        return decimal_value


class BrokerPosition(BaseModel):
    symbol: str
    qty: Decimal
    market_value: Decimal
    current_price: Decimal | None = None
    asset_class: str = "stock"
    side: str = "long"

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("qty", "market_value", "current_price", mode="before")
    @classmethod
    def _validate_decimals(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        decimal_value = _to_decimal(value)
        if decimal_value < 0:
            raise ValueError("position values must be non-negative")
        return decimal_value


class BrokerOrderRequest(BaseModel):
    symbol: str
    side: str
    order_type: str = "market"
    time_in_force: str = "day"
    qty: Decimal | None = None
    notional: Decimal | None = None
    client_order_id: str | None = None
    extended_hours: bool = False
    metadata: dict = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("qty", "notional", mode="before")
    @classmethod
    def _validate_qty_or_notional(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        if value is None:
            return None
        decimal_value = _to_decimal(value)
        if decimal_value <= 0:
            raise ValueError("qty and notional must be greater than zero")
        return decimal_value


class BrokerOrderResult(BaseModel):
    order_id: str
    symbol: str
    side: str
    status: str
    submitted_at: datetime | None = None
    raw_response: dict = Field(default_factory=dict)


class Broker(Protocol):
    dry_run: bool

    def get_account(self) -> BrokerAccount:
        ...

    def get_positions(self) -> list[BrokerPosition]:
        ...

    def translate_order_intent(
        self, intent: OrderIntent, mandate: PortfolioMandate
    ) -> BrokerOrderRequest:
        ...

    def submit_order_intents(
        self, intents: list[OrderIntent], mandate: PortfolioMandate
    ) -> list[BrokerOrderResult]:
        ...

    def get_orders(self, *, status: str = "all", limit: int = 50) -> list[BrokerOrderResult]:
        ...
