# Copilot Instructions for portfolio-optimizer

## Project Overview
This is an experimentation repository for financial optimization problems using MOSEK Fusion API. The project uses abstract base class patterns to implement modular optimization solvers for portfolio rebalancing, focusing on Sharpe ratio maximization and mean-variance optimization.

## Architecture & Component Structure

### Core Design Pattern: Abstract Optimizer Interface
- **File**: [src/core/optimizers/ioptimizer.py](src/core/optimizers/ioptimizer.py)
- All optimizers implement `IOptimizer` abstract base class with single `optimize(rebalance_problem)` method
- Enables pluggable optimizer implementations for different problem types

### Optimizer Implementations
- **Location**: `src/core/optimizers/<optimizer_name>/`
- Each optimizer subdirectory contains:
  - `<optimizer_name>.py` - main optimizer class inheriting from `IOptimizer`
  - Uses MOSEK Fusion API with `Model()` context manager
  - Contains model logic: variables, constraints, objective, and solve call

### Key Optimizers
- **MaximizeSharpeOptimizer**: [src/core/optimizers/maximize_sharp_optimizer/maximize_sharpe.py](src/core/optimizers/maximize_sharp_optimizer/maximize_sharpe.py)
  - Currently has template code commented out with mathematical formulation
  - Uses variable change: `y = x / (μ^T*x - rf)` to convert non-convex Sharpe ratio problem to convex QP
  - Recovery: `x_i = y_i / Σ(y_j)`
- **MeanVarianceOptimizer**: [src/core/optimizers/mean_variance_optimizer/mean_variance_optimizer.py](src/core/optimizers/mean_variance_optimizer/mean_variance_optimizer.py)
  - Incomplete - placeholder for efficient frontier generation

### Data Structures
- **RebalanceProblem**: [src/portfolio/rebalance_problem.py](src/portfolio/rebalance_problem.py)
  - Pure data container with prepared portfolio inputs
  - Properties: `tickers`, `mean_vector`, `covariance_matrix`, `risk_free_rate`, `target_weights`, `initial_holdings`, etc.
  - No external calls or transformations—use `RebalanceProblemBuilder` to construct
- **RebalanceProblemBuilder**: [src/portfolio/rebalance_problem_builder.py](src/portfolio/rebalance_problem_builder.py)
  - Orchestrates the data pipeline: fetch market data → transform → calculate statistics → build RebalanceProblem
  - Separates concerns: fetching (MarketDataGateway) + calculations (PortfolioCalculations) + encapsulation (RebalanceProblem)
- **PortfolioCalculations**: [src/portfolio/portfolio_calculations.py](src/portfolio/portfolio_calculations.py)
  - Static utility methods for portfolio statistics (returns, mean, covariance) and parameter extraction

## Key Technologies & Dependencies
- **mosek (Fusion API)** - Commercial optimization solver
- **gurobipy 13.0.0** - Gurobi solver (listed but MOSEK is active optimizer)
- **pandas 2.3.3** - Data manipulation
- **numpy 1.26.4** - Numerical computations
- **scikit-learn, statsmodels** - Statistical analysis

## Developer Workflows

### Environment Setup
1. Virtual environment: `.venv/` directory in root
2. Install dependencies: `pip install -r requirements.txt`
3. **License Requirements**: MOSEK requires API key; Gurobi requires license setup

### Running Code
- Entry point: [src/main.py](src/main.py)
- Pattern: Create config dict → use `RebalanceProblemBuilder` to build `RebalanceProblem` → pass to optimizer
- Example: `builder = RebalanceProblemBuilder(config); problem = builder.build(); optimizer.optimize(problem)`

### Import Pattern
- Optimizers: `from core.optimizers.maximize_sharp_optimizer.maximize_sharpe import MaximizeSharpeOptimizer`
- Data construction: `from portfolio.rebalance_problem_builder import RebalanceProblemBuilder`
- Data model: `from portfolio.rebalance_problem import RebalanceProblem`
- Use absolute imports from `src/` root level
## Copilot instructions — portfolio-optimizer

This repository is an experimental toolkit for portfolio rebalancing and optimization (Sharpe-maximization, mean-variance). The codebase is small and opinionated: a pipeline builds a clean `RebalanceProblem` which optimizer implementations consume and a backtesting engine evaluates.

Quick run (from project root)
- Create and activate virtualenv, install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- Set `PYTHONPATH` to `src` or run as module. Examples (PowerShell):

```powershell
# $env:PYTHONPATH = 'src' ; python src\main.py
python -m src.main
```

MOSEK / Solver notes
- MOSEK Fusion is used by optimizers. A valid MOSEK license (or API key) is required; set the vendor-provided environment variables (e.g. `MOSEKLM_LICENSE_FILE`) per MOSEK docs. Gurobi also appears in requirements and needs a license if used.

Key components & where to look
- `src/portfolio/rebalance_problem_builder.py`: orchestrates fetching market data (via `infrastructure/market_data/marketdatagateway.py`), computing statistics (`portfolio/portfolio_calculations.py`) and producing `RebalanceProblem` (`src/portfolio/rebalance_problem.py`).
- `src/core/optimizers/ioptimizer.py`: optimizer interface — implement `optimize(rebalance_problem)`.
- `src/core/optimizers/<name>/`: optimizer implementations live here. See `maximize_sharp_optimizer/maximize_sharpe.py` for a MOSEK Fusion template and `mean_variance_optimizer/mean_variance_optimizer.py` as a placeholder.
- `src/core/optimizers/optimizer_factory.py`: factory mapping from `program_type` to optimizer class (note: `fixed_weights` is currently mapped to `None`).
- `src/backtesting/backtesting_engine.py`: backtesting harness and portfolio wrappers (`FixedWeightPortfolio`, `MaxSharpePortfolio`).

Repository patterns to follow
- Data flow: RebalanceProblemBuilder -> RebalanceProblem -> Optimizer -> BacktestingEngine. Keep these boundaries clear: builders prepare pure data, optimizers do optimization only.
- MOSEK usage pattern: use `with Model(...) as M:`, define variables with `Domain.*`, add constraints, set objective, call `M.solve()`, read variables via `.level()`.
- Import style: code uses absolute imports from the `src` package (e.g., `from core.optimizers...`). Running via `python -m src.main` or setting `PYTHONPATH=src` ensures imports resolve.

Developer tasks specific to this repo
- Add new optimizer: create `src/core/optimizers/<name>/`, implement class inheriting `IOptimizer`, register class in `optimizer_factory._optimizers`, run via `program_type` in `src/main.py` config.
- If modifying data ingestion, update `marketdatagateway.py` and `RebalanceProblemBuilder` together — builder expects cleaned numeric arrays (`mean_vector`, `covariance_matrix`, `risk_free_rate`).

Recommended quick checks for AI edits
- Search for `Model(` / `mosek.fusion` when changing optimizers.
- Check `optimizer_factory._optimizers` mapping after adding a new class.
- Ensure `RebalanceProblem` public attributes are used (e.g. `problem.mean_vector`) — builders expose properties, not `get_*` methods.

What this file does not cover
- This repo has no CI/tests folder included — add unit tests when modifying core calculations or optimizer logic.
- License setup for MOSEK/Gurobi is environment-specific; include vendor steps in a follow-up if you want them embedded here.

If any of the environment assumptions are incorrect (preferred run command, CI usage, or required env vars), tell me what to include and I will iterate.
- Check if `Model.solve()` completes without exception
