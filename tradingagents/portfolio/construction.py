from __future__ import annotations

from decimal import Decimal

from .constraints import EPSILON as CONSTRAINT_EPSILON
from .models import PositionTarget

EPSILON = Decimal("0.000001")


def _copy_targets_with_weights(
    targets: list[PositionTarget], weights: list[Decimal]
) -> list[PositionTarget]:
    return [
        target.model_copy(update={"target_weight": weight})
        for target, weight in zip(targets, weights, strict=True)
    ]


def normalize_weights(targets: list[PositionTarget]) -> list[PositionTarget]:
    if not targets:
        return []

    total_weight = sum((target.target_weight for target in targets), Decimal("0"))
    if total_weight <= 0:
        raise ValueError("target weights must sum to a positive value")

    normalized_weights = [target.target_weight / total_weight for target in targets]
    return _copy_targets_with_weights(targets, normalized_weights)


def cap_weights(
    targets: list[PositionTarget], max_position_weight: Decimal
) -> list[PositionTarget]:
    if not targets:
        return []
    if max_position_weight <= 0 or max_position_weight > 1:
        raise ValueError("max_position_weight must be between 0 and 1")
    if Decimal(len(targets)) * max_position_weight + EPSILON < Decimal("1"):
        raise ValueError("position cap is infeasible for the number of targets")

    working_targets = normalize_weights(targets)
    weights = [target.target_weight for target in working_targets]

    while True:
        violating_indices = [
            index
            for index, weight in enumerate(weights)
            if weight > max_position_weight + EPSILON
        ]
        if not violating_indices:
            break

        excess = Decimal("0")
        for index in violating_indices:
            excess += weights[index] - max_position_weight
            weights[index] = max_position_weight

        eligible_indices = [
            index for index in range(len(weights)) if index not in violating_indices
        ]
        if not eligible_indices:
            if excess > EPSILON:
                raise ValueError("position cap leaves no room to redistribute weight")
            break

        eligible_total = sum((weights[index] for index in eligible_indices), Decimal("0"))
        if eligible_total <= 0:
            raise ValueError("cannot redistribute capped weight without eligible positions")

        for index in eligible_indices:
            weights[index] += excess * (weights[index] / eligible_total)

    return normalize_weights(_copy_targets_with_weights(working_targets, weights))


def apply_sector_caps(
    targets: list[PositionTarget], max_sector_weight: Decimal
) -> list[PositionTarget]:
    if not targets:
        return []
    if max_sector_weight <= 0 or max_sector_weight > 1:
        raise ValueError("max_sector_weight must be between 0 and 1")

    working_targets = normalize_weights(targets)
    weights = [target.target_weight for target in working_targets]

    for _ in range((len(working_targets) * 4) + 1):
        sector_indices: dict[str, list[int]] = {}
        for index, target in enumerate(working_targets):
            sector = target.sector or "UNKNOWN"
            sector_indices.setdefault(sector, []).append(index)

        violations = {
            sector: sum((weights[index] for index in indices), Decimal("0"))
            for sector, indices in sector_indices.items()
            if sum((weights[index] for index in indices), Decimal("0")) > max_sector_weight + EPSILON
        }
        if not violations:
            return normalize_weights(_copy_targets_with_weights(working_targets, weights))

        excess = Decimal("0")
        locked_indices: set[int] = set()
        for sector, sector_total in violations.items():
            scale = max_sector_weight / sector_total
            for index in sector_indices[sector]:
                new_weight = weights[index] * scale
                excess += weights[index] - new_weight
                weights[index] = new_weight
                locked_indices.add(index)

        eligible_indices = [
            index for index in range(len(weights)) if index not in locked_indices
        ]
        if not eligible_indices:
            raise ValueError("sector caps are infeasible for the selected targets")

        eligible_total = sum((weights[index] for index in eligible_indices), Decimal("0"))
        if eligible_total <= 0:
            raise ValueError("cannot redistribute sector excess without eligible targets")

        for index in eligible_indices:
            weights[index] += excess * (weights[index] / eligible_total)

    raise ValueError("sector cap normalization did not converge")


def build_equal_weight_targets(
    symbols: list[str],
    *,
    asset_type: str = "stock",
    sector_by_symbol: dict[str, str] | None = None,
    price_by_symbol: dict[str, Decimal] | None = None,
    liquidity_by_symbol: dict[str, Decimal] | None = None,
) -> list[PositionTarget]:
    if not symbols:
        return []

    equal_weight = Decimal("1") / Decimal(len(symbols))
    sector_by_symbol = sector_by_symbol or {}
    price_by_symbol = price_by_symbol or {}
    liquidity_by_symbol = liquidity_by_symbol or {}

    return [
        PositionTarget(
            symbol=symbol,
            target_weight=equal_weight,
            asset_type=asset_type,
            sector=sector_by_symbol.get(symbol),
            price=price_by_symbol.get(symbol),
            avg_dollar_volume=liquidity_by_symbol.get(symbol),
        )
        for symbol in symbols
    ]


def build_constrained_targets(
    targets: list[PositionTarget],
    *,
    max_position_weight: Decimal,
    max_sector_weight: Decimal,
) -> list[PositionTarget]:
    normalized_targets = normalize_weights(targets)

    for _ in range((len(normalized_targets) * 6) + 1):
        previous_weights = [target.target_weight for target in normalized_targets]
        normalized_targets = cap_weights(normalized_targets, max_position_weight)
        normalized_targets = apply_sector_caps(normalized_targets, max_sector_weight)
        normalized_targets = normalize_weights(normalized_targets)

        max_position = max(
            (target.target_weight for target in normalized_targets),
            default=Decimal("0"),
        )
        sector_totals: dict[str, Decimal] = {}
        for target in normalized_targets:
            sector = target.sector or "UNKNOWN"
            sector_totals[sector] = sector_totals.get(sector, Decimal("0")) + target.target_weight

        max_sector = max(sector_totals.values(), default=Decimal("0"))
        current_weights = [target.target_weight for target in normalized_targets]
        stable = all(
            abs(current - previous) <= CONSTRAINT_EPSILON
            for current, previous in zip(current_weights, previous_weights, strict=True)
        )
        if (
            max_position <= max_position_weight + CONSTRAINT_EPSILON
            and max_sector <= max_sector_weight + CONSTRAINT_EPSILON
            and stable
        ):
            return normalized_targets

    raise ValueError("unable to satisfy position and sector caps simultaneously")
