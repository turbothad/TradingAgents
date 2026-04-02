from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.portfolio.models import DecisionRecord, PortfolioMandate
from tradingagents.portfolio.orchestrator import PortfolioOrchestrator
from tradingagents.storage import load_mandate, save_decision_record, save_model, save_model_list

from .common import parse_symbols, resolve_output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create target portfolio allocations from a mandate and a symbol universe."
    )
    parser.add_argument("--mandate-file", required=True, help="Path to a PortfolioMandate JSON file.")
    parser.add_argument("--symbols", help="Comma-separated symbol list.")
    parser.add_argument("--symbols-file", help="Path to a newline-delimited symbol file.")
    parser.add_argument(
        "--strategy",
        choices=["equal-weight", "research"],
        default="equal-weight",
        help="Use deterministic equal weighting or score symbols through TradingAgents.",
    )
    parser.add_argument("--analysis-date", default=date.today().isoformat(), help="Analysis date in YYYY-MM-DD format.")
    parser.add_argument("--portfolio-id", default="paper-pm", help="Stable portfolio identifier.")
    parser.add_argument("--output-dir", help="Directory to store targets and audit files.")
    parser.add_argument("--llm-provider", help="Override DEFAULT_CONFIG llm_provider.")
    parser.add_argument("--deep-model", help="Override DEFAULT_CONFIG deep_think_llm.")
    parser.add_argument("--quick-model", help="Override DEFAULT_CONFIG quick_think_llm.")
    parser.add_argument("--max-debate-rounds", type=int, help="Override debate rounds for research strategy.")
    parser.add_argument(
        "--selected-analysts",
        default="market,social,news,fundamentals",
        help="Comma-separated analyst list for research strategy.",
    )
    return parser


def load_or_create_mandate(path: str) -> PortfolioMandate:
    mandate_path = Path(path)
    if mandate_path.exists():
        return load_mandate(mandate_path)
    raise FileNotFoundError(f"Mandate file not found: {mandate_path}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    mandate = load_or_create_mandate(args.mandate_file)
    symbols = parse_symbols(args.symbols, args.symbols_file)
    output_dir = resolve_output_dir(
        provided=args.output_dir,
        portfolio_id=args.portfolio_id,
        run_kind="create",
    )

    config = DEFAULT_CONFIG.copy()
    if args.llm_provider:
        config["llm_provider"] = args.llm_provider
    if args.deep_model:
        config["deep_think_llm"] = args.deep_model
    if args.quick_model:
        config["quick_think_llm"] = args.quick_model
    if args.max_debate_rounds is not None:
        config["max_debate_rounds"] = args.max_debate_rounds

    orchestrator = PortfolioOrchestrator(
        config=config,
        selected_analysts=[item.strip() for item in args.selected_analysts.split(",") if item.strip()],
        debug=False,
    )

    try:
        if args.strategy == "research":
            ideas = orchestrator.analyze_candidates(symbols, as_of=args.analysis_date)
            targets = orchestrator.build_targets(mandate, ideas)
            save_model_list(ideas, output_dir / "candidate_ideas.json")
            candidate_payload = [idea.model_dump(mode="json") for idea in ideas]
            human_summary = f"Built {len(targets)} targets from {len(ideas)} research-scored symbols."
        else:
            targets = orchestrator.build_equal_weight_targets(mandate, symbols)
            candidate_payload = []
            human_summary = f"Built {len(targets)} equal-weight targets from {len(symbols)} symbols."
    except Exception as exc:
        print(f"Failed to create portfolio targets: {exc}", file=sys.stderr)
        return 2

    save_model(mandate, output_dir / "mandate.json")
    save_model_list(targets, output_dir / "targets.json")

    decision_record = DecisionRecord(
        decision_id=uuid.uuid4().hex,
        portfolio_id=args.portfolio_id,
        timestamp=datetime.combine(
            date.fromisoformat(args.analysis_date),
            datetime.min.time(),
            tzinfo=UTC,
        ),
        inputs_hash=f"{args.strategy}:{','.join(symbols)}:{args.analysis_date}",
        mandate_snapshot=mandate.model_dump(mode="json"),
        candidate_set=candidate_payload,
        target_positions=[target.model_dump(mode="json") for target in targets],
        rebalance_plan={},
        human_summary=human_summary,
    )
    save_decision_record(decision_record, output_dir / "decision_record.json")

    print(json.dumps(
        {
            "portfolio_id": args.portfolio_id,
            "strategy": args.strategy,
            "analysis_date": args.analysis_date,
            "targets_file": str(output_dir / "targets.json"),
            "mandate_file": str(output_dir / "mandate.json"),
            "decision_record_file": str(output_dir / "decision_record.json"),
            "target_count": len(targets),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
