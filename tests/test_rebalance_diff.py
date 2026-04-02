import unittest
from decimal import Decimal

from tradingagents.portfolio.mandate import create_mandate
from tradingagents.portfolio.models import CurrentPosition, PositionTarget
from tradingagents.portfolio.rebalance import diff_targets_vs_current, make_rebalance_plan


class RebalanceDiffTests(unittest.TestCase):
    def setUp(self):
        self.mandate = create_mandate(
            starting_cash="10000",
            risk_profile="aggressive",
            time_horizon_days=365,
            max_positions=5,
            max_position_weight="1.0",
            max_sector_weight="1.0",
        )

    def test_builds_buy_orders_from_cash(self):
        target_positions = [
            PositionTarget(
                symbol="AAPL",
                target_weight="0.6",
                sector="Technology",
                avg_dollar_volume="5000000",
                price="100",
            ),
            PositionTarget(
                symbol="XLF",
                target_weight="0.4",
                asset_type="etf",
                sector="Financials",
                avg_dollar_volume="5000000",
                price="50",
            ),
        ]

        plan = make_rebalance_plan(
            self.mandate,
            [],
            target_positions,
        )

        self.assertEqual(len(plan.orders), 2)
        self.assertEqual(plan.orders[0].symbol, "AAPL")
        self.assertEqual(plan.orders[0].side, "buy")
        self.assertEqual(plan.orders[0].notional_delta, Decimal("6000.0"))
        self.assertEqual(plan.orders[0].quantity_delta, Decimal("60.0"))
        self.assertEqual(plan.orders[1].notional_delta, Decimal("4000.0"))
        self.assertEqual(plan.orders[1].quantity_delta, Decimal("80.0"))

    def test_rebalance_diff_generates_buy_and_sell(self):
        current_positions = [
            CurrentPosition(symbol="AAPL", quantity="50", market_value="5000", sector="Technology", price="100"),
            CurrentPosition(symbol="MSFT", quantity="50", market_value="5000", sector="Technology", price="100"),
        ]
        target_positions = [
            PositionTarget(
                symbol="AAPL",
                target_weight="0.7",
                sector="Technology",
                avg_dollar_volume="5000000",
                price="100",
            ),
            PositionTarget(
                symbol="MSFT",
                target_weight="0.3",
                sector="Technology",
                avg_dollar_volume="5000000",
                price="100",
            ),
        ]

        orders = diff_targets_vs_current(
            current_positions,
            target_positions,
            total_equity=Decimal("10000"),
        )

        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].side, "buy")
        self.assertEqual(orders[0].notional_delta, Decimal("2000.0"))
        self.assertEqual(orders[0].quantity_delta, Decimal("20.0"))
        self.assertEqual(orders[1].side, "sell")
        self.assertEqual(orders[1].notional_delta, Decimal("2000.0"))
        self.assertEqual(orders[1].quantity_delta, Decimal("20.0"))

    def test_no_trade_plan_when_targets_match_holdings(self):
        current_positions = [
            CurrentPosition(symbol="AAPL", quantity="50", market_value="5000", sector="Technology", price="100"),
            CurrentPosition(symbol="XLF", quantity="100", market_value="5000", sector="Financials", price="50"),
        ]
        target_positions = [
            PositionTarget(
                symbol="AAPL",
                target_weight="0.5",
                sector="Technology",
                avg_dollar_volume="5000000",
                price="100",
            ),
            PositionTarget(
                symbol="XLF",
                target_weight="0.5",
                asset_type="etf",
                sector="Financials",
                avg_dollar_volume="5000000",
                price="50",
            ),
        ]

        plan = make_rebalance_plan(
            self.mandate,
            current_positions,
            target_positions,
            total_equity="10000",
        )

        self.assertEqual(plan.orders, [])
        self.assertEqual(plan.turnover, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
