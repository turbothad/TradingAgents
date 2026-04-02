from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .models import ConstraintCheck, PortfolioMandate, PositionTarget

EPSILON = Decimal("0.000001")


class PortfolioConstraintError(ValueError):
    pass


def check_long_only(targets: list[PositionTarget]) -> ConstraintCheck:
    has_invalid_weight = any(target.target_weight < 0 for target in targets)
    return ConstraintCheck(
        name="long_only",
        passed=not has_invalid_weight,
        details="all target weights are non-negative" if not has_invalid_weight else "negative target weights are not allowed",
    )


def check_target_weight_sum(targets: list[PositionTarget]) -> ConstraintCheck:
    total_weight = sum((target.target_weight for target in targets), Decimal("0"))
    if not targets:
        return ConstraintCheck(
            name="weight_sum",
            passed=True,
            details="empty target set keeps the portfolio in cash",
        )

    passed = abs(total_weight - Decimal("1")) <= EPSILON
    return ConstraintCheck(
        name="weight_sum",
        passed=passed,
        details=f"target weights sum to {total_weight}",
    )


def check_position_count(
    mandate: PortfolioMandate, targets: list[PositionTarget]
) -> ConstraintCheck:
    count = len(targets)
    min_positions = mandate.min_positions or 0
    passed = min_positions <= count <= mandate.max_positions
    return ConstraintCheck(
        name="position_count",
        passed=passed,
        details=f"position count is {count}, allowed range is {min_positions} to {mandate.max_positions}",
    )


def check_max_position_weight(
    mandate: PortfolioMandate, targets: list[PositionTarget]
) -> ConstraintCheck:
    violations = [
        f"{target.symbol}={target.target_weight}"
        for target in targets
        if target.target_weight > mandate.max_position_weight + EPSILON
    ]
    return ConstraintCheck(
        name="max_position_weight",
        passed=not violations,
        details="; ".join(violations) if violations else "all positions are within the position cap",
    )


def check_max_sector_weight(
    mandate: PortfolioMandate, targets: list[PositionTarget]
) -> ConstraintCheck:
    sector_weights: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for target in targets:
        sector = target.sector or "UNKNOWN"
        sector_weights[sector] += target.target_weight

    violations = [
        f"{sector}={weight}"
        for sector, weight in sorted(sector_weights.items())
        if weight > mandate.max_sector_weight + EPSILON
    ]
    return ConstraintCheck(
        name="max_sector_weight",
        passed=not violations,
        details="; ".join(violations) if violations else "all sectors are within the sector cap",
    )


def check_allowed_assets(
    mandate: PortfolioMandate, targets: list[PositionTarget]
) -> ConstraintCheck:
    disallowed = [
        f"{target.symbol}={target.asset_type}"
        for target in targets
        if target.asset_type not in mandate.allowed_asset_types
    ]
    return ConstraintCheck(
        name="allowed_assets",
        passed=not disallowed,
        details="; ".join(disallowed) if disallowed else "all targets use allowed asset types",
    )


def check_liquidity(
    mandate: PortfolioMandate, targets: list[PositionTarget]
) -> ConstraintCheck:
    illiquid = []
    for target in targets:
        if target.avg_dollar_volume is None:
            illiquid.append(f"{target.symbol}=missing")
        elif target.avg_dollar_volume + EPSILON < mandate.min_avg_dollar_volume:
            illiquid.append(f"{target.symbol}={target.avg_dollar_volume}")

    return ConstraintCheck(
        name="liquidity",
        passed=not illiquid,
        details="; ".join(illiquid) if illiquid else "all targets pass the liquidity threshold",
    )


def check_turnover_limit(
    mandate: PortfolioMandate, turnover: Decimal
) -> ConstraintCheck:
    passed = turnover <= mandate.max_turnover_per_rebalance + EPSILON
    return ConstraintCheck(
        name="turnover",
        passed=passed,
        details=(
            f"turnover {turnover} is within the limit {mandate.max_turnover_per_rebalance}"
            if passed
            else f"turnover {turnover} exceeds the limit {mandate.max_turnover_per_rebalance}"
        ),
    )


def evaluate_targets_against_mandate(
    mandate: PortfolioMandate,
    targets: list[PositionTarget],
    turnover: Decimal | None = None,
) -> list[ConstraintCheck]:
    checks = [
        check_long_only(targets),
        check_target_weight_sum(targets),
        check_position_count(mandate, targets),
        check_allowed_assets(mandate, targets),
        check_max_position_weight(mandate, targets),
        check_max_sector_weight(mandate, targets),
        check_liquidity(mandate, targets),
    ]
    if turnover is not None:
        checks.append(check_turnover_limit(mandate, turnover))
    return checks


def validate_targets_against_mandate(
    mandate: PortfolioMandate,
    targets: list[PositionTarget],
    turnover: Decimal | None = None,
) -> list[ConstraintCheck]:
    checks = evaluate_targets_against_mandate(mandate, targets, turnover=turnover)
    failures = [check for check in checks if not check.passed]
    if failures:
        failure_summary = "; ".join(f"{check.name}: {check.details}" for check in failures)
        raise PortfolioConstraintError(failure_summary)
    return checks
