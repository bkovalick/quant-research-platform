# Quant Research Platform

A config-driven backtesting platform for systematic strategies. You define an experiment in JSON, it runs signal generation, portfolio optimization, and backtesting, then produces performance metrics, factor attribution, and Excel reports.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.10+. Uses numpy, pandas, scipy, scikit-learn, cvxpy, yfinance, pandas_datareader, fastapi, duckdb, openpyxl.

## Running

```bash
python src/run_local.py
```

Or with the UI:

```bash
cd src && uvicorn application.controller:app --reload   # :8000
cd frontend && npm install && npm run dev               # :5173
```

## How it works

An experiment config lists one or more strategies. For each one the runner builds market state from price data, constructs signals, assembles a rebalance problem, and steps a backtest loop forward through time. The engine advances a cursor day by day, drifts portfolio weights with realized returns, and calls the strategy on rebalance dates to get new target weights. Results go to DuckDB and optionally to an Excel report.

```text
src/
├── run_local.py
├── application/          FastAPI routes, ExperimentRunner
├── config/               experiment_*.json
├── domain/
│   ├── machine_learning/ FeatureBuilder, CrossSectionalModel (Ridge), ReturnPredictor
│   ├── optimizers/       CVXPY-based portfolio optimizer
│   ├── portfolio/        weights, returns, turnover over time
│   ├── signals/          momentum, mean reversion, Black-Litterman, ML, vol forecast, pairs
│   └── strategies/       turn signals into target weights
├── infrastructure/       yfinance gateway, DuckDB persistence
├── models/               data containers (RebalanceProblem, BacktestResult, StrategyRun)
├── reference/            asset class and sector maps
├── reporting/            PerformanceAnalyzer, diagnostics, Excel export
├── services/             factories, RebalanceProblemBuilder, SignalFactory
├── simulation/           BacktestingEngine, MarketState, parameter sweeps
└── utils/                lookback windows, rebalance step logic
```

## Config

Strategies separate what they trade from what they look at:

- `investment_universe` — what the optimizer can hold
- `signal_universe` — what features are computed on (defaults to the investment universe)
- `exogenous_tickers` — inputs like ^VIX that feed signals but are never allocated to

```json
"market_state_config": {
  "lookback_window_key": "1y",
  "market_frequency": "d",
  "cash_allocation": 0.05,
  "investment_universe": ["AAPL", "MSFT"],
  "exogenous_tickers": ["^VIX"]
}
```

## Usage

```python
import json
from application.experiment_runner import ExperimentRunner

with open("src/config/experiment_full_suite.json") as f:
    config = json.load(f)

experiment = ExperimentRunner(config).run_parallel()
```

Per strategy that resolves to:

```python
problem   = RebalanceProblemBuilder(rebalance_config, market_state).build()
optimizer = OptimizerFactory.create_optimizer(problem.optimizer_type)
strategy  = StrategyFactory.create_strategy(problem, optimizer)

run = BacktestingEngine(portfolio, strategy, market_state, signal_factory, benchmark).run_backtest(problem)
```

## Metrics and diagnostics

`PerformanceAnalyzer` produces annualized return, volatility, Sharpe, Sortino, Calmar, tracking error, information ratio, VaR/CVaR, drawdown stats, and turnover.

Diagnostics run alongside, depending on strategy type:

- `LongOnlyICDiagnostics` — Spearman IC series, IC IR, hit rate, AR(1) half-life, t-test
- `PairsSpreadDiagnostics` — IC from entry z-score against realized spread return
- `FactorRegressionDiagnostics` — Fama-French 5-factor regression with Newey-West standard errors, reporting alpha and factor loadings

## Frontend

A collapsible nav rail with three destinations. The Lab is a drawer holding experiment configuration and the per-strategy editor. Results and Attribution are full-width pages.

Results shows a strategy table, a cumulative wealth chart with benchmark overlay and a date-range slider, risk/tail/drawdown tabs, and a statistical evidence section covering performance, factor attribution, and robustness. Attribution breaks return into factor contributions and plots rolling loadings.

## Conventions

Models are data containers — calculations belong in builders, services, or domain classes. Imports are absolute from the `src` root, never relative. To add a strategy or optimizer, implement it under the matching `domain/` package and register it in the corresponding factory under `services/`.
