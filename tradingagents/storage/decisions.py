from __future__ import annotations

import json
from pathlib import Path

from tradingagents.portfolio.models import DecisionRecord


def save_decision_record(record: DecisionRecord, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return destination


def load_decision_record(input_path: str | Path) -> DecisionRecord:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    return DecisionRecord.model_validate(payload)
