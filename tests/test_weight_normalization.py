import unittest
from decimal import Decimal

from tradingagents.portfolio.construction import build_constrained_targets, cap_weights, normalize_weights
from tradingagents.portfolio.models import PositionTarget


class WeightNormalizationTests(unittest.TestCase):
    def test_normalize_weights_sums_to_one(self):
        targets = [
            PositionTarget(symbol="AAPL", target_weight="2", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="MSFT", target_weight="1", sector="Technology", avg_dollar_volume="5000000"),
        ]

        normalized = normalize_weights(targets)

        total_weight = sum((target.target_weight for target in normalized), Decimal("0"))
        self.assertEqual(total_weight, Decimal("1"))
        self.assertEqual(normalized[0].target_weight, Decimal("0.6666666666666666666666666667"))

    def test_cap_weights_redistributes_excess(self):
        targets = [
            PositionTarget(symbol="AAPL", target_weight="0.8", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="XLF", target_weight="0.2", asset_type="etf", sector="Financials", avg_dollar_volume="5000000"),
        ]

        capped = cap_weights(targets, Decimal("0.6"))

        self.assertEqual(capped[0].target_weight, Decimal("0.6"))
        self.assertEqual(capped[1].target_weight, Decimal("0.4"))

    def test_normalize_weights_handles_empty_inputs(self):
        self.assertEqual(normalize_weights([]), [])

    def test_build_constrained_targets_respects_position_and_sector_caps(self):
        targets = [
            PositionTarget(symbol="AAPL", target_weight="1", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="MSFT", target_weight="1", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="META", target_weight="1", sector="Communication Services", avg_dollar_volume="5000000"),
            PositionTarget(symbol="SPY", target_weight="1", asset_type="etf", sector="Large Blend", avg_dollar_volume="5000000"),
        ]

        constrained = build_constrained_targets(
            targets,
            max_position_weight=Decimal("0.30"),
            max_sector_weight=Decimal("0.50"),
        )

        self.assertTrue(all(target.target_weight <= Decimal("0.30") for target in constrained))
        technology_weight = sum(
            target.target_weight
            for target in constrained
            if target.sector == "Technology"
        )
        self.assertTrue(technology_weight <= Decimal("0.50"))

    def test_build_constrained_targets_raises_for_infeasible_mix(self):
        targets = [
            PositionTarget(symbol="AAPL", target_weight="1", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="MSFT", target_weight="1", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="NVDA", target_weight="1", sector="Technology", avg_dollar_volume="5000000"),
            PositionTarget(symbol="META", target_weight="1", sector="Communication Services", avg_dollar_volume="5000000"),
            PositionTarget(symbol="SPY", target_weight="1", asset_type="etf", sector="Large Blend", avg_dollar_volume="5000000"),
        ]

        with self.assertRaises(ValueError):
            build_constrained_targets(
                targets,
                max_position_weight=Decimal("0.25"),
                max_sector_weight=Decimal("0.40"),
            )


if __name__ == "__main__":
    unittest.main()
