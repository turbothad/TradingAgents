from __future__ import annotations

from decimal import Decimal

from .models import CandidateIdea, PositionTarget


RATING_TO_SCORE = {
    "BUY": Decimal("1.0"),
    "OVERWEIGHT": Decimal("0.8"),
    "HOLD": Decimal("0.5"),
    "UNDERWEIGHT": Decimal("0.2"),
    "SELL": Decimal("0.0"),
}


def score_rating(rating: str) -> Decimal:
    normalized = rating.strip().upper()
    if normalized not in RATING_TO_SCORE:
        raise ValueError(f"Unsupported rating: {rating}")
    return RATING_TO_SCORE[normalized]


def rank_candidates(ideas: list[CandidateIdea]) -> list[CandidateIdea]:
    return sorted(
        ideas,
        key=lambda idea: (
            idea.score,
            idea.confidence,
            idea.avg_dollar_volume or Decimal("0"),
            idea.symbol,
        ),
        reverse=True,
    )


def candidate_to_target(candidate: CandidateIdea, target_weight: Decimal) -> PositionTarget:
    return PositionTarget(
        symbol=candidate.symbol,
        target_weight=target_weight,
        asset_type=candidate.asset_type,
        sector=candidate.sector,
        thesis_summary=candidate.thesis_summary,
        machine_rationale=candidate.machine_rationale,
        price=candidate.machine_rationale.get("price"),
        avg_dollar_volume=candidate.avg_dollar_volume,
    )
