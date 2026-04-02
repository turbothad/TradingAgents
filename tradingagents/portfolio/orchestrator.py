from __future__ import annotations

from datetime import date
from decimal import ROUND_CEILING, Decimal
from itertools import combinations
from typing import Any

import yfinance as yf

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from .construction import build_constrained_targets
from .models import CandidateIdea, PortfolioMandate, PositionTarget
from .ranking import candidate_to_target, rank_candidates, score_rating


class PortfolioOrchestrator:
    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        selected_analysts: list[str] | None = None,
        debug: bool = False,
    ):
        self.config = (config or DEFAULT_CONFIG).copy()
        self.selected_analysts = selected_analysts or ["market", "social", "news", "fundamentals"]
        self.debug = debug

    def analyze_candidates(
        self,
        symbols: list[str],
        *,
        as_of: str | None = None,
    ) -> list[CandidateIdea]:
        if not symbols:
            return []

        analysis_date = as_of or date.today().isoformat()
        graph = TradingAgentsGraph(
            selected_analysts=self.selected_analysts,
            debug=self.debug,
            config=self.config,
        )

        candidate_ideas: list[CandidateIdea] = []
        for symbol in symbols:
            final_state, rating = graph.propagate(symbol, analysis_date)
            metadata = self._fetch_market_snapshot(symbol)
            candidate_ideas.append(
                CandidateIdea(
                    symbol=symbol,
                    asset_type=metadata["asset_type"],
                    sector=metadata["sector"],
                    score=score_rating(rating),
                    confidence=_confidence_from_rating(rating),
                    thesis_summary=final_state["final_trade_decision"],
                    avg_dollar_volume=metadata["avg_dollar_volume"],
                    research_artifact_refs=[],
                    machine_rationale={
                        "rating": rating,
                        "price": metadata["price"],
                        "analysis_date": analysis_date,
                        "market_report": final_state.get("market_report", ""),
                        "sentiment_report": final_state.get("sentiment_report", ""),
                        "news_report": final_state.get("news_report", ""),
                        "fundamentals_report": final_state.get("fundamentals_report", ""),
                        "investment_plan": final_state.get("investment_plan", ""),
                        "final_trade_decision": final_state.get("final_trade_decision", ""),
                    },
                )
            )

        return rank_candidates(candidate_ideas)

    def build_targets(
        self,
        mandate: PortfolioMandate,
        ideas: list[CandidateIdea],
    ) -> list[PositionTarget]:
        eligible = [
            idea
            for idea in rank_candidates(ideas)
            if idea.asset_type in mandate.allowed_asset_types
            and idea.avg_dollar_volume is not None
            and idea.avg_dollar_volume >= mandate.min_avg_dollar_volume
            and idea.score > Decimal("0")
        ]

        if not eligible:
            raise ValueError("No candidates passed the mandate filters")

        selected = _find_feasible_candidate_set(mandate, eligible)
        equal_weight = Decimal("1") / Decimal(len(selected))
        preliminary_targets = [candidate_to_target(candidate, equal_weight) for candidate in selected]
        return build_constrained_targets(
            preliminary_targets,
            max_position_weight=mandate.max_position_weight,
            max_sector_weight=mandate.max_sector_weight,
        )

    def build_equal_weight_targets(
        self,
        mandate: PortfolioMandate,
        symbols: list[str],
    ) -> list[PositionTarget]:
        snapshots = [self._fetch_market_snapshot(symbol) for symbol in symbols]
        candidates = [
            CandidateIdea(
                symbol=symbol,
                asset_type=snapshot["asset_type"],
                sector=snapshot["sector"],
                score=Decimal("1"),
                confidence=Decimal("1"),
                thesis_summary=f"Equal-weight seed allocation for {symbol}.",
                avg_dollar_volume=snapshot["avg_dollar_volume"],
                machine_rationale={
                    "price": snapshot["price"],
                    "source": "equal_weight_seed",
                },
            )
            for symbol, snapshot in zip(symbols, snapshots, strict=True)
        ]
        return self.build_targets(mandate, candidates)

    def _fetch_market_snapshot(self, symbol: str) -> dict[str, Any]:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1mo", auto_adjust=False)
        if history.empty:
            raise ValueError(f"No market data available for {symbol}")

        latest_close = Decimal(str(history["Close"].dropna().iloc[-1]))
        avg_dollar_volume = Decimal(
            str(((history["Close"] * history["Volume"]).dropna()).mean())
        )

        asset_type = "stock"
        sector = None
        try:
            info = ticker.info or {}
            quote_type = str(info.get("quoteType", "")).lower()
            if quote_type == "etf":
                asset_type = "etf"
            sector = info.get("sector") or info.get("category")
        except Exception:
            sector = None

        return {
            "asset_type": asset_type,
            "sector": sector,
            "price": latest_close,
            "avg_dollar_volume": avg_dollar_volume,
        }


def _confidence_from_rating(rating: str) -> Decimal:
    normalized = rating.strip().upper()
    if normalized == "HOLD":
        return Decimal("0.5")
    if normalized in {"BUY", "OVERWEIGHT"}:
        return Decimal("0.8")
    if normalized in {"UNDERWEIGHT", "SELL"}:
        return Decimal("0.7")
    return Decimal("0.0")


def _find_feasible_candidate_set(
    mandate: PortfolioMandate,
    eligible: list[CandidateIdea],
) -> list[CandidateIdea]:
    if not eligible:
        raise ValueError("No eligible candidates supplied")

    min_count = max(
        mandate.min_positions or 1,
        int((Decimal("1") / mandate.max_position_weight).to_integral_value(rounding=ROUND_CEILING)),
    )
    max_count = min(mandate.max_positions, len(eligible))
    pool = eligible[: min(len(eligible), mandate.max_positions + 8)]

    for target_count in range(max_count, min_count - 1, -1):
        for combo in combinations(range(len(pool)), target_count):
            selected = [pool[index] for index in combo]
            equal_weight = Decimal("1") / Decimal(len(selected))
            try:
                build_constrained_targets(
                    [candidate_to_target(candidate, equal_weight) for candidate in selected],
                    max_position_weight=mandate.max_position_weight,
                    max_sector_weight=mandate.max_sector_weight,
                )
            except ValueError:
                continue
            return selected

    raise ValueError("Unable to find a feasible candidate set under the mandate constraints")
