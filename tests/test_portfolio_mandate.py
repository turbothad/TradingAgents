import unittest
from decimal import Decimal

from pydantic import ValidationError

from tradingagents.portfolio.mandate import create_mandate


class PortfolioMandateTests(unittest.TestCase):
    def test_create_mandate_applies_profile_defaults(self):
        mandate = create_mandate(
            starting_cash="10000",
            risk_profile="balanced",
            time_horizon_days=365,
            max_positions=8,
        )

        self.assertEqual(mandate.max_position_weight, Decimal("0.2"))
        self.assertEqual(mandate.max_sector_weight, Decimal("0.35"))
        self.assertEqual(mandate.rebalance_cadence, "weekly")
        self.assertEqual(mandate.benchmark_symbols, ["SPY"])

    def test_long_only_mandate_rejects_shorts(self):
        with self.assertRaises(ValidationError):
            create_mandate(
                starting_cash="10000",
                risk_profile="balanced",
                time_horizon_days=365,
                max_positions=8,
                allow_short=True,
            )

    def test_mandate_rejects_invalid_position_bounds(self):
        with self.assertRaises(ValidationError):
            create_mandate(
                starting_cash="10000",
                risk_profile="balanced",
                time_horizon_days=365,
                max_positions=4,
                min_positions=5,
            )


if __name__ == "__main__":
    unittest.main()
