import unittest
from decimal import Decimal

from tradingagents.portfolio.constraints import PortfolioConstraintError, validate_targets_against_mandate
from tradingagents.portfolio.mandate import create_mandate
from tradingagents.portfolio.models import CurrentPosition, PositionTarget
from tradingagents.portfolio.rebalance import compute_current_weights, compute_turnover


class PortfolioConstraintTests(unittest.TestCase):
    def setUp(self):
        self.mandate = create_mandate(
            starting_cash="10000",
            risk_profile="balanced",
            time_horizon_days=365,
            max_positions=5,
        )

    def test_sector_cap_failure_is_detected(self):
        targets = [
            PositionTarget(
                symbol="AAPL",
                target_weight="0.50",
                sector="Technology",
                avg_dollar_volume="5000000",
            ),
            PositionTarget(
                symbol="MSFT",
                target_weight="0.50",
                sector="Technology",
                avg_dollar_volume="5000000",
            ),
        ]

        with self.assertRaises(PortfolioConstraintError):
            validate_targets_against_mandate(self.mandate, targets)

    def test_position_cap_failure_is_detected(self):
        targets = [
            PositionTarget(
                symbol="AAPL",
                target_weight="0.25",
                sector="Technology",
                avg_dollar_volume="5000000",
            ),
            PositionTarget(
                symbol="XLF",
                target_weight="0.75",
                asset_type="etf",
                sector="Financials",
                avg_dollar_volume="5000000",
            ),
        ]

        with self.assertRaises(PortfolioConstraintError):
            validate_targets_against_mandate(self.mandate, targets)

    def test_turnover_limit_failure_is_detected(self):
        conservative_mandate = create_mandate(
            starting_cash="10000",
            risk_profile="conservative",
            time_horizon_days=365,
            max_positions=5,
            max_position_weight="1.0",
            max_sector_weight="1.0",
        )
        current_positions = compute_current_weights(
            [
                CurrentPosition(symbol="AAPL", quantity="50", market_value="5000", sector="Technology", price="100"),
                CurrentPosition(symbol="MSFT", quantity="50", market_value="5000", sector="Technology", price="100"),
            ],
            total_equity=Decimal("10000"),
        )
        target_positions = [
            PositionTarget(
                symbol="AAPL",
                target_weight="1.0",
                sector="Technology",
                avg_dollar_volume="5000000",
                price="100",
            )
        ]

        turnover = compute_turnover(current_positions, target_positions)

        with self.assertRaises(PortfolioConstraintError):
            validate_targets_against_mandate(
                conservative_mandate,
                target_positions,
                turnover=turnover,
            )


if __name__ == "__main__":
    unittest.main()
