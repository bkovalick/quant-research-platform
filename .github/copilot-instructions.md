
# Copilot Instructions — portfolio-optimizer

## Project Overview
This repository is an experimental toolkit for portfolio rebalancing and optimization, focusing on Sharpe ratio maximization and mean-variance optimization. It uses modular, pluggable optimizer classes (MOSEK Fusion API) and a clear data pipeline for reproducible experiments.

## Architecture & Key Patterns
- **Data pipeline:**
  - [src/portfolio/rebalance_problem_builder.py](src/portfolio/rebalance_problem_builder.py) orchestrates fetching market data, computing statistics, and building a pure data container ([src/portfolio/rebalance_problem.py](src/portfolio/rebalance_problem.py)).
  - Builders prepare all numeric/statistical inputs; no logic in data containers.
- **Optimizers:**
  - All optimizers implement `IOptimizer` ([src/core/optimizers/ioptimizer.py](src/core/optimizers/ioptimizer.py)) with a single `optimize(rebalance_problem)` method.
  - Implementations live in `src/core/optimizers/<name>/`, e.g. [maximize_sharp_optimizer/maximize_sharpe.py](src/core/optimizers/maximize_sharp_optimizer/maximize_sharpe.py).
  - Use MOSEK Fusion: always use `with Model() as M:` context, define variables with `Domain.*`, add constraints, set objective, call `M.solve()`, extract results via `.level()`.
  - Register new optimizers in [optimizer_factory.py](src/core/optimizers/optimizer_factory.py) for use via config.
- **Backtesting:**
  - [src/backtesting/backtesting_engine.py](src/backtesting/backtesting_engine.py) runs backtests using portfolio wrappers (e.g. `FixedWeightPortfolio`, `MaxSharpePortfolio`).
- **Import conventions:**
  - Use absolute imports from the `src` root (e.g. `from core.optimizers...`).
  - Run as `python -m src.main` or set `PYTHONPATH=src` for import resolution.

## Developer Workflows
- **Setup:**
  - Create and activate a virtualenv in root: `.venv/`
  - Install dependencies: `pip install -r requirements.txt`
  - MOSEK and Gurobi require licenses (see vendor docs; set env vars as needed).
- **Run:**
  - Entry point: [src/main.py](src/main.py)
  - Typical pattern: build config dict → use `RebalanceProblemBuilder` → pass to optimizer → run backtest.
  - Example:
    ```python
    builder = RebalanceProblemBuilder(config)
    problem = builder.build()
    optimizer.optimize(problem)
    ```
- **Adding an optimizer:**
  - Create a new subdir in `src/core/optimizers/`, implement class inheriting `IOptimizer`.
  - Register in `optimizer_factory._optimizers`.
  - Use MOSEK Fusion idioms as above.
- **Data ingestion:**
  - Update both `marketdatagateway.py` and `RebalanceProblemBuilder` if changing data sources or formats.
  - Builders expect cleaned numpy arrays for all statistics.

## Project-Specific Conventions
- **No business logic in data containers** (e.g. `RebalanceProblem` is pure data; all calculations in builder or utility modules).
- **Absolute imports only**; never use relative imports.
- **Keep boundaries clear:**
  - Builders: data prep only
  - Optimizers: optimization only
  - Backtesting: evaluation only
- **MOSEK Fusion usage:** always use context manager, never global model objects.

## Quick AI Checks
- When editing optimizers, search for `Model(` or `mosek.fusion` to ensure correct usage.
- After adding an optimizer, check `optimizer_factory._optimizers` mapping.
- Use public attributes of `RebalanceProblem` (e.g. `problem.mean_vector`), not `get_*` methods.

## Not Included
- No CI/tests by default — add unit tests for new core logic.
- License setup for MOSEK/Gurobi is environment-specific.

---
If any section is unclear or incomplete, please provide feedback for further iteration.
