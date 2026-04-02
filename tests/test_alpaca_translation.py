import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from tradingagents.broker.alpaca_paper import (
    AlpacaPaperBroker,
    BrokerConfigurationError,
)
from tradingagents.portfolio.mandate import create_mandate
from tradingagents.portfolio.models import OrderIntent


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class AlpacaTranslationTests(unittest.TestCase):
    def setUp(self):
        self.mandate = create_mandate(
            starting_cash="10000",
            risk_profile="balanced",
            time_horizon_days=365,
            max_positions=8,
            allow_fractional=True,
        )

    def test_rejects_live_base_url(self):
        with self.assertRaises(BrokerConfigurationError):
            AlpacaPaperBroker(
                api_key="key",
                secret_key="secret",
                base_url="https://api.alpaca.markets",
                dry_run=True,
            )

    def test_translate_order_intent_uses_fractional_qty(self):
        broker = AlpacaPaperBroker(
            api_key="key",
            secret_key="secret",
            dry_run=True,
        )
        intent = OrderIntent(
            symbol="AAPL",
            side="buy",
            target_weight_before="0",
            target_weight_after="0.5",
            quantity_delta="12.3456789",
            notional_delta="1234.56",
            reason_code="new_position",
            human_reason="Seed position",
        )

        request = broker.translate_order_intent(intent, self.mandate)

        self.assertEqual(request.symbol, "AAPL")
        self.assertEqual(request.side, "buy")
        self.assertEqual(request.qty, Decimal("12.345679"))
        self.assertIsNone(request.notional)

    def test_dry_run_submit_returns_synthetic_results(self):
        broker = AlpacaPaperBroker(
            api_key="key",
            secret_key="secret",
            dry_run=True,
        )
        intent = OrderIntent(
            symbol="MSFT",
            side="sell",
            target_weight_before="0.4",
            target_weight_after="0.2",
            quantity_delta="5",
            notional_delta="500",
            reason_code="decrease",
            human_reason="Trim position",
        )

        results = broker.submit_order_intents([intent], self.mandate)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "dry_run")
        self.assertEqual(results[0].symbol, "MSFT")

    def test_fetches_account_and_positions_from_api(self):
        session = MagicMock()
        session.request.side_effect = [
            FakeResponse(
                {
                    "id": "acct-1",
                    "cash": "1000",
                    "buying_power": "1000",
                    "equity": "1000",
                    "currency": "USD",
                    "trading_blocked": False,
                }
            ),
            FakeResponse(
                [
                    {
                        "symbol": "AAPL",
                        "qty": "3",
                        "market_value": "510",
                        "current_price": "170",
                        "asset_class": "us_equity",
                        "side": "long",
                    }
                ]
            ),
        ]
        broker = AlpacaPaperBroker(
            api_key="key",
            secret_key="secret",
            dry_run=False,
            session=session,
        )

        account = broker.get_account()
        positions = broker.get_positions()

        self.assertEqual(account.account_id, "acct-1")
        self.assertEqual(account.equity, Decimal("1000"))
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, "AAPL")


if __name__ == "__main__":
    unittest.main()
