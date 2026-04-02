from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from tradingagents.broker import AlpacaPaperBroker
from tradingagents.broker.alpaca_paper import BrokerConfigurationError, BrokerExecutionError
from tradingagents.portfolio.models import CurrentPosition, DecisionRecord
from tradingagents.portfolio.rebalance import make_rebalance_plan
from tradingagents.storage import (
    load_mandate,
    load_position_targets,
    save_decision_record,
    save_model,
    save_model_list,
)

from .common import resolve_output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diff target allocations against Alpaca paper positions and optionally submit orders."
    )
    parser.add_argument("--mandate-file", required=True, help="Path to a PortfolioMandate JSON file.")
    parser.add_argument("--targets-file", required=True, help="Path to a PositionTarget JSON file.")
    parser.add_argument("--portfolio-id", default="paper-pm", help="Stable portfolio identifier.")
    parser.add_argument("--output-dir", help="Directory to store rebalance artifacts.")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit orders to Alpaca paper trading. Default behavior is dry-run.",
    )
    parser.add_argument(
        "--min-trade-notional",
        default="0",
        help="Minimum trade size in dollars before an order intent is emitted.",
    )
    return parser


def _broker_positions_to_current_positions(
    broker_positions,
) -> list[CurrentPosition]:
    return [
        CurrentPosition(
            symbol=position.symbol,
            quantity=position.qty,
            market_value=position.market_value,
            price=position.current_price,
            asset_type="stock",
        )
        for position in broker_positions
    ]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    mandate = load_mandate(args.mandate_file)
    targets = load_position_targets(args.targets_file)
    output_dir = resolve_output_dir(
        provided=args.output_dir,
        portfolio_id=args.portfolio_id,
        run_kind="rebalance",
    )

    try:
        broker = AlpacaPaperBroker.from_env(dry_run=not args.submit)
        account = broker.get_account()
    except (BrokerConfigurationError, BrokerExecutionError) as exc:
        print(f"Broker configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Failed to fetch Alpaca account state: {exc}", file=sys.stderr)
        return 3

    if account.trading_blocked:
        print("Alpaca paper account is trading blocked.", file=sys.stderr)
        return 4

    try:
        broker_positions = broker.get_positions()
        current_positions = _broker_positions_to_current_positions(broker_positions)
        plan = make_rebalance_plan(
            mandate,
            current_positions,
            targets,
            total_equity=account.equity,
            min_trade_notional=Decimal(args.min_trade_notional),
        )
    except Exception as exc:
        print(f"Failed to build rebalance plan: {exc}", file=sys.stderr)
        return 5

    estimated_buy_notional = sum(
        (order.notional_delta for order in plan.orders if order.side == "buy"),
        Decimal("0"),
    )
    estimated_sell_notional = sum(
        (order.notional_delta for order in plan.orders if order.side == "sell"),
        Decimal("0"),
    )
    if args.submit and estimated_buy_notional > account.buying_power + estimated_sell_notional:
        print(
            "Refusing to submit orders that exceed available buying power after estimated sells.",
            file=sys.stderr,
        )
        return 6

    try:
        order_results = broker.submit_order_intents(plan.orders, mandate)
    except Exception as exc:
        print(f"Failed to submit order intents: {exc}", file=sys.stderr)
        return 7

    save_model(mandate, output_dir / "mandate.json")
    save_model_list(current_positions, output_dir / "current_positions.json")
    save_model_list(targets, output_dir / "targets.json")
    save_model(plan, output_dir / "rebalance_plan.json")

    decision_record = DecisionRecord(
        decision_id=uuid.uuid4().hex,
        portfolio_id=args.portfolio_id,
        timestamp=datetime.now(UTC),
        inputs_hash=f"rebalance:{args.targets_file}:{account.equity}",
        mandate_snapshot=mandate.model_dump(mode="json"),
        candidate_set=[],
        target_positions=[target.model_dump(mode="json") for target in targets],
        rebalance_plan=plan.model_dump(mode="json"),
        human_summary=plan.summary,
    )
    save_decision_record(decision_record, output_dir / "decision_record.json")
    save_model_list(order_results, output_dir / "order_results.json")

    print(
        json.dumps(
            {
                "portfolio_id": args.portfolio_id,
                "dry_run": broker.dry_run,
                "account_equity": str(account.equity),
                "order_count": len(plan.orders),
                "turnover": str(plan.turnover),
                "rebalance_plan_file": str(output_dir / "rebalance_plan.json"),
                "order_results_file": str(output_dir / "order_results.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
