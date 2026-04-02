# Portfolio Paper Trading Workflow

This fork now includes a portfolio-building and Alpaca paper-trading workflow alongside the original single-symbol TradingAgents CLI.

## Prerequisites

Create and activate the local environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set Alpaca paper credentials:

```bash
export ALPACA_API_KEY=...
export ALPACA_SECRET_KEY=...
export ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

If you want the AI research path instead of deterministic equal weighting, also set one supported LLM provider key, for example:

```bash
export OPENAI_API_KEY=...
```

## 1. Create Target Allocations

Equal-weight seed portfolio from a symbol list:

```bash
ta-create-portfolio \
  --mandate-file examples/portfolio_mandate.sample.json \
  --symbols-file examples/seed_symbols.sample.txt \
  --strategy equal-weight \
  --portfolio-id sample-pm
```

Research-scored portfolio using the existing TradingAgents graph:

```bash
ta-create-portfolio \
  --mandate-file examples/portfolio_mandate.sample.json \
  --symbols-file examples/seed_symbols.sample.txt \
  --strategy research \
  --analysis-date 2026-04-02 \
  --portfolio-id sample-pm \
  --llm-provider openai \
  --deep-model gpt-5.4 \
  --quick-model gpt-5.4-mini
```

This command writes:

- `mandate.json`
- `targets.json`
- `decision_record.json`
- `candidate_ideas.json` for research runs

under `results/portfolio_runs/<portfolio-id>/create-<timestamp>/`.

## 2. Inspect Targets

```bash
ta-explain-portfolio \
  --targets-file results/portfolio_runs/sample-pm/create-<timestamp>/targets.json
```

## 3. Dry-Run a Rebalance Against Alpaca Paper

```bash
ta-rebalance-portfolio \
  --mandate-file results/portfolio_runs/sample-pm/create-<timestamp>/mandate.json \
  --targets-file results/portfolio_runs/sample-pm/create-<timestamp>/targets.json
```

Default behavior is dry-run. The command will:

- fetch Alpaca paper account state
- fetch current paper positions
- compute the rebalance diff
- validate mandate constraints
- save `rebalance_plan.json`, `order_results.json`, and `decision_record.json`

under `results/portfolio_runs/<portfolio-id>/rebalance-<timestamp>/`.

## 4. Submit Paper Orders

```bash
ta-rebalance-portfolio \
  --mandate-file results/portfolio_runs/sample-pm/create-<timestamp>/mandate.json \
  --targets-file results/portfolio_runs/sample-pm/create-<timestamp>/targets.json \
  --submit
```

Safety behavior:

- live Alpaca URLs are rejected
- short and margin-enabled mandates are rejected
- dry-run is the default
- oversized submissions that exceed estimated buying power are rejected

## Sample Files

- `examples/portfolio_mandate.sample.json`
- `examples/seed_symbols.sample.txt`
- `examples/targets.sample.json`
