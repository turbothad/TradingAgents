from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tradingagents.storage import load_position_targets, load_rebalance_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print a human-readable summary of saved targets or a rebalance plan."
    )
    parser.add_argument("--plan-file", help="Path to a saved RebalancePlan JSON file.")
    parser.add_argument("--targets-file", help="Path to a saved PositionTarget JSON file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if bool(args.plan_file) == bool(args.targets_file):
        parser.error("Provide exactly one of --plan-file or --targets-file")

    if args.plan_file:
        plan = load_rebalance_plan(args.plan_file)
        payload = {
            "summary": plan.summary,
            "turnover": str(plan.turnover),
            "orders": [order.model_dump(mode="json") for order in plan.orders],
            "constraint_checks": [
                check.model_dump(mode="json") for check in plan.constraint_checks
            ],
        }
    else:
        targets = load_position_targets(args.targets_file)
        payload = {
            "target_count": len(targets),
            "targets": [
                {
                    "symbol": target.symbol,
                    "target_weight": str(target.target_weight),
                    "sector": target.sector,
                    "thesis_summary": target.thesis_summary,
                }
                for target in targets
            ],
        }

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
