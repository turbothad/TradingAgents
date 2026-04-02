from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tradingagents.default_config import DEFAULT_CONFIG


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def resolve_output_dir(
    *,
    provided: str | None,
    portfolio_id: str,
    run_kind: str,
) -> Path:
    if provided:
        output_dir = Path(provided)
    else:
        output_dir = (
            Path(DEFAULT_CONFIG["results_dir"])
            / "portfolio_runs"
            / portfolio_id
            / f"{run_kind}-{timestamp_slug()}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def parse_symbols(symbols: str | None, symbols_file: str | None) -> list[str]:
    if symbols and symbols_file:
        raise ValueError("Provide either --symbols or --symbols-file, not both")
    if not symbols and not symbols_file:
        raise ValueError("One of --symbols or --symbols-file is required")

    if symbols:
        raw_symbols = symbols.split(",")
    else:
        raw_symbols = Path(symbols_file).read_text(encoding="utf-8").splitlines()

    normalized = [symbol.strip().upper() for symbol in raw_symbols if symbol.strip()]
    if not normalized:
        raise ValueError("No symbols were provided")
    return normalized
