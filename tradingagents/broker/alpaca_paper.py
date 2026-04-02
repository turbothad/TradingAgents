from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_DOWN
from typing import Any

import requests

from tradingagents.portfolio.models import OrderIntent, PortfolioMandate

from .base import (
    Broker,
    BrokerAccount,
    BrokerOrderRequest,
    BrokerOrderResult,
    BrokerPosition,
)


DEFAULT_ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"


class BrokerConfigurationError(ValueError):
    pass


class BrokerExecutionError(RuntimeError):
    pass


class AlpacaPaperBroker(Broker):
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        base_url: str = DEFAULT_ALPACA_PAPER_URL,
        dry_run: bool = True,
        timeout_seconds: int = 15,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip()
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

        if not self.api_key or not self.secret_key:
            raise BrokerConfigurationError("Alpaca API credentials are required")
        if not self._is_paper_url(self.base_url):
            raise BrokerConfigurationError(
                f"Refusing to use non-paper Alpaca endpoint: {self.base_url}"
            )

    @classmethod
    def from_env(
        cls,
        *,
        dry_run: bool = True,
        session: requests.Session | None = None,
    ) -> "AlpacaPaperBroker":
        api_key = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
        secret_key = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
        base_url = (
            os.getenv("ALPACA_BASE_URL")
            or os.getenv("APCA_API_BASE_URL")
            or DEFAULT_ALPACA_PAPER_URL
        )
        return cls(
            api_key=api_key or "",
            secret_key=secret_key or "",
            base_url=base_url,
            dry_run=dry_run,
            session=session,
        )

    @staticmethod
    def _is_paper_url(base_url: str) -> bool:
        normalized = base_url.lower()
        return "paper-api.alpaca.markets" in normalized or normalized.endswith("/paper")

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
            json=json_body,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_account(self) -> BrokerAccount:
        payload = self._request("GET", "/v2/account")
        return BrokerAccount(
            account_id=payload["id"],
            cash=payload["cash"],
            buying_power=payload["buying_power"],
            equity=payload["equity"],
            currency=payload.get("currency", "USD"),
            is_paper=self._is_paper_url(self.base_url),
            trading_blocked=payload.get("trading_blocked", False),
        )

    def get_positions(self) -> list[BrokerPosition]:
        payload = self._request("GET", "/v2/positions")
        positions: list[BrokerPosition] = []
        for item in payload:
            side = item.get("side", "long")
            if side != "long":
                raise BrokerExecutionError(
                    f"Refusing to manage non-long Alpaca position for {item.get('symbol')}"
                )
            positions.append(
                BrokerPosition(
                    symbol=item["symbol"],
                    qty=item["qty"],
                    market_value=item["market_value"],
                    current_price=item.get("current_price"),
                    asset_class=item.get("asset_class", "stock"),
                    side=side,
                )
            )
        return positions

    def translate_order_intent(
        self, intent: OrderIntent, mandate: PortfolioMandate
    ) -> BrokerOrderRequest:
        if intent.side == "sell" and intent.target_weight_after > intent.target_weight_before:
            raise BrokerExecutionError(f"Inconsistent sell intent for {intent.symbol}")
        if intent.side == "buy" and intent.target_weight_after < intent.target_weight_before:
            raise BrokerExecutionError(f"Inconsistent buy intent for {intent.symbol}")
        if mandate.allow_short:
            raise BrokerExecutionError("Broker adapter refuses short-enabled mandates")
        if mandate.allow_margin:
            raise BrokerExecutionError("Broker adapter refuses margin-enabled mandates")

        quantity = intent.quantity_delta
        notional = intent.notional_delta

        if mandate.allow_fractional:
            if quantity is not None:
                quantity = quantity.quantize(Decimal("0.000001"))
        else:
            if quantity is None:
                raise BrokerExecutionError(
                    f"Non-fractional trading requires quantity for {intent.symbol}"
                )
            quantity = quantity.quantize(Decimal("1"), rounding=ROUND_DOWN)
            if quantity <= 0:
                raise BrokerExecutionError(
                    f"Rounded quantity is zero for non-fractional order {intent.symbol}"
                )
            notional = None

        if quantity is None and notional is None:
            raise BrokerExecutionError(
                f"Order intent for {intent.symbol} is missing quantity and notional"
            )

        return BrokerOrderRequest(
            symbol=intent.symbol,
            side=intent.side,
            qty=quantity,
            notional=None if quantity is not None else notional,
            client_order_id=f"pm-{intent.symbol.lower()}-{uuid.uuid4().hex[:20]}",
            metadata={
                "reason_code": intent.reason_code,
                "human_reason": intent.human_reason,
                "before_weight": str(intent.target_weight_before),
                "after_weight": str(intent.target_weight_after),
            },
        )

    def submit_order_intents(
        self, intents: list[OrderIntent], mandate: PortfolioMandate
    ) -> list[BrokerOrderResult]:
        requests_to_submit = [
            self.translate_order_intent(intent, mandate)
            for intent in intents
        ]

        if self.dry_run:
            return [
                BrokerOrderResult(
                    order_id=f"dryrun-{request.client_order_id}",
                    symbol=request.symbol,
                    side=request.side,
                    status="dry_run",
                    submitted_at=datetime.now(UTC),
                    raw_response=request.model_dump(mode="json"),
                )
                for request in requests_to_submit
            ]

        account = self.get_account()
        if account.trading_blocked:
            raise BrokerExecutionError("Alpaca paper account is trading blocked")

        results: list[BrokerOrderResult] = []
        for request in requests_to_submit:
            payload = {
                "symbol": request.symbol,
                "side": request.side,
                "type": request.order_type,
                "time_in_force": request.time_in_force,
                "client_order_id": request.client_order_id,
                "extended_hours": request.extended_hours,
            }
            if request.qty is not None:
                payload["qty"] = str(request.qty.normalize())
            elif request.notional is not None:
                payload["notional"] = str(request.notional.normalize())

            response = self._request("POST", "/v2/orders", json_body=payload)
            results.append(
                BrokerOrderResult(
                    order_id=response["id"],
                    symbol=response["symbol"],
                    side=response["side"],
                    status=response["status"],
                    submitted_at=_parse_datetime(response.get("submitted_at")),
                    raw_response=response,
                )
            )
        return results

    def get_orders(self, *, status: str = "all", limit: int = 50) -> list[BrokerOrderResult]:
        payload = self._request(
            "GET",
            "/v2/orders",
            params={"status": status, "limit": limit, "direction": "desc"},
        )
        return [
            BrokerOrderResult(
                order_id=item["id"],
                symbol=item["symbol"],
                side=item["side"],
                status=item["status"],
                submitted_at=_parse_datetime(item.get("submitted_at")),
                raw_response=item,
            )
            for item in payload
        ]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
