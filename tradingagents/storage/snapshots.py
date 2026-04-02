from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from tradingagents.portfolio.models import CurrentPosition, PortfolioMandate, PositionTarget, RebalancePlan

ModelT = TypeVar("ModelT", bound=BaseModel)


def save_model(model: BaseModel, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return destination


def load_model(model_type: type[ModelT], input_path: str | Path) -> ModelT:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    return model_type.model_validate(payload)


def save_model_list(models: list[BaseModel], output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps([model.model_dump(mode="json") for model in models], indent=2),
        encoding="utf-8",
    )
    return destination


def load_position_targets(input_path: str | Path) -> list[PositionTarget]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    return TypeAdapter(list[PositionTarget]).validate_python(payload)


def load_current_positions(input_path: str | Path) -> list[CurrentPosition]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    return TypeAdapter(list[CurrentPosition]).validate_python(payload)


def load_mandate(input_path: str | Path) -> PortfolioMandate:
    return load_model(PortfolioMandate, input_path)


def load_rebalance_plan(input_path: str | Path) -> RebalancePlan:
    return load_model(RebalancePlan, input_path)
