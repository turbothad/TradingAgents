from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from .constraints import evaluate_targets_against_mandate, validate_targets_against_mandate
from .construction import build_constrained_targets
from .models import (
    CurrentPosition,
    OrderIntent,
    PortfolioMandate,
    PositionTarget,
    RebalancePlan,
)

EPSILON = Decimal("0.000001")


def compute_current_weights(
    current_positions: list[CurrentPosition],
    *,
    total_equity: Decimal | int | float | str | None = None,
) -> list[CurrentPosition]:
    if total_equity is None:
        total_equity_value = sum(
            (position.market_value for position in current_positions), Decimal("0")
        )
    else:
        total_equity_value = Decimal(str(total_equity))

    if not current_positions:
        return []
    if total_equity_value <= 0:
        raise ValueError("total_equity must be positive when current positions exist")

    return [
        position.model_copy(
            update={"current_weight": position.market_value / total_equity_value}
        )
        for position in current_positions
    ]


def compute_turnover(
    current_positions: list[CurrentPosition],
    target_positions: list[PositionTarget],
) -> Decimal:
    if not current_positions:
        return Decimal("0")

    current_weights = {
        position.symbol: position.current_weight or Decimal("0")
        for position in current_positions
    }
    target_weights = {target.symbol: target.target_weight for target in target_positions}

    all_symbols = sorted(set(current_weights) | set(target_weights))
    total_difference = sum(
        (
            abs(target_weights.get(symbol, Decimal("0")) - current_weights.get(symbol, Decimal("0")))
            for symbol in all_symbols
        ),
        Decimal("0"),
    )
    return total_difference / Decimal("2")


def _resolve_reference_price(
    current_position: CurrentPosition | None, target_position: PositionTarget | None
) -> Decimal | None:
    if target_position and target_position.price:
        return target_position.price
    if current_position and current_position.price:
        return current_position.price
    if current_position and current_position.quantity > 0:
        return current_position.market_value / current_position.quantity
    return None


def build_order_intents(
    current_positions: list[CurrentPosition],
    target_positions: list[PositionTarget],
    *,
    total_equity: Decimal | int | float | str,
    min_trade_notional: Decimal | int | float | str = Decimal("0"),
) -> list[OrderIntent]:
    total_equity_value = Decimal(str(total_equity))
    min_trade_notional_value = Decimal(str(min_trade_notional))
    current_by_symbol = {position.symbol: position for position in current_positions}
    target_by_symbol = {target.symbol: target for target in target_positions}

    ordered_symbols = [
        target.symbol for target in target_positions
    ] + [
        position.symbol
        for position in current_positions
        if position.symbol not in target_by_symbol
    ]

    orders: list[OrderIntent] = []
    for symbol in ordered_symbols:
        current_position = current_by_symbol.get(symbol)
        target_position = target_by_symbol.get(symbol)

        before_weight = (
            current_position.current_weight if current_position and current_position.current_weight is not None else Decimal("0")
        )
        after_weight = target_position.target_weight if target_position else Decimal("0")
        weight_delta = after_weight - before_weight
        notional_delta = abs(weight_delta * total_equity_value)

        if notional_delta <= min_trade_notional_value + EPSILON:
            continue

        side = "buy" if weight_delta > 0 else "sell"
        reason_code = "increase"
        if before_weight <= EPSILON and after_weight > 0:
            reason_code = "new_position"
        elif after_weight <= EPSILON and before_weight > 0:
            reason_code = "exit"
        elif side == "sell":
            reason_code = "decrease"

        reference_price = _resolve_reference_price(current_position, target_position)
        quantity_delta = (
            notional_delta / reference_price
            if reference_price and reference_price > 0
            else None
        )

        orders.append(
            OrderIntent(
                symbol=symbol,
                side=side,
                target_weight_before=before_weight,
                target_weight_after=after_weight,
                quantity_delta=quantity_delta,
                notional_delta=notional_delta,
                reason_code=reason_code,
                human_reason=(
                    f"{side.upper()} {symbol} to move from {before_weight:.2%} to {after_weight:.2%} target weight"
                ),
            )
        )

    return orders


def diff_targets_vs_current(
    current_positions: list[CurrentPosition],
    target_positions: list[PositionTarget],
    *,
    total_equity: Decimal | int | float | str,
    min_trade_notional: Decimal | int | float | str = Decimal("0"),
) -> list[OrderIntent]:
    weighted_positions = compute_current_weights(
        current_positions, total_equity=total_equity
    )
    return build_order_intents(
        weighted_positions,
        target_positions,
        total_equity=total_equity,
        min_trade_notional=min_trade_notional,
    )


def make_rebalance_plan(
    mandate: PortfolioMandate,
    current_positions: list[CurrentPosition],
    target_positions: list[PositionTarget],
    *,
    as_of: datetime | None = None,
    total_equity: Decimal | int | float | str | None = None,
    min_trade_notional: Decimal | int | float | str = Decimal("0"),
) -> RebalancePlan:
    plan_timestamp = as_of or datetime.now(UTC)
    portfolio_value = (
        Decimal(str(total_equity))
        if total_equity is not None
        else sum((position.market_value for position in current_positions), Decimal("0"))
    )
    if portfolio_value <= 0:
        portfolio_value = mandate.starting_cash

    normalized_current_positions = compute_current_weights(
        current_positions, total_equity=portfolio_value
    )
    constrained_targets = build_constrained_targets(
        target_positions,
        max_position_weight=mandate.max_position_weight,
        max_sector_weight=mandate.max_sector_weight,
    )
    turnover = compute_turnover(normalized_current_positions, constrained_targets)
    constraint_checks = evaluate_targets_against_mandate(
        mandate,
        constrained_targets,
        turnover=turnover,
    )
    validate_targets_against_mandate(
        mandate,
        constrained_targets,
        turnover=turnover,
    )
    orders = build_order_intents(
        normalized_current_positions,
        constrained_targets,
        total_equity=portfolio_value,
        min_trade_notional=min_trade_notional,
    )

    summary = (
        "No trades required; current holdings already match the target portfolio."
        if not orders
        else f"Generated {len(orders)} order intents across {len(constrained_targets)} target positions."
    )

    return RebalancePlan(
        as_of=plan_timestamp,
        current_positions=normalized_current_positions,
        target_positions=constrained_targets,
        orders=orders,
        turnover=turnover,
        constraint_checks=constraint_checks,
        summary=summary,
    )
