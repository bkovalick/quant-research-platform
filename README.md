# Portfolio Optimizer

## Overview

Portfolio Optimizer is a modular Python toolkit for portfolio rebalancing, optimization, and backtesting. It supports experiment-driven workflows, strategy evaluation, and reporting, using CVXPY for optimization. The architecture is designed for extensibility, reproducibility, and clear separation of concerns.

## Project Structure

```
src/
├── main.py
├── controller.py
├── application/
│   ├── experiment_runner.py
├── config/
│   ├── experiment_config.json
├── infrastructure/
│   ├── market_data_gateway.py
├── reference/
│   ├── market_metadata.py
├── domain/
│   ├── optimizers/
│   │   ├── ioptimizer.py
│   │   ├── portfolio_optimizer.py
│   ├── portfolio/
│   │   ├── iportfolio.py
│   │   ├── portfolio.py
│   ├── signals/
│   │   ├── signals.py
│   ├── strategies/
│   │   ├── equal_weight_strategy.py
│   │   ├── fixed_weight_strategy.py
│   │   ├── istrategy.py
│   │   ├── mean_variance_strategy.py
├── models/
│   ├── backtest_result.py
│   ├── experiment.py
│   ├── market_config.py
│   ├── rebalance_problem.py
│   ├── rebalance_solution.py
│   ├── signals_config.py
│   ├── strategy_run.py
├── reporting/
│   ├── reporting_module.py
├── services/
│   ├── optimizer_factory.py
│   ├── rebalance_problem_builder.py
│   ├── strategy_factory.py
├── simulation/
│   ├── backtesting_engine.py
│   ├── market_state.py
├── utils/
│   ├── lookback_windows.py
│   ├── rebalance_steps.py
```

## Key Modules & Their Purpose

- **main.py**: Entry point for running experiments and orchestrating workflows.
- **application/**: Contains experiment runner and application-level orchestration.
- **config/**: Stores configuration files and settings for experiments.
- **infrastructure/**: Market data ingestion (yfinance, CSV).
- **reference/**: Static market metadata (universe, asset class maps).
- **domain/**:
  - **optimizers/**: Defines optimizer interfaces and implementations.
  - **portfolio/**: Portfolio abstractions and interfaces.
  - **signals/**: Signal generation and processing.
  - **strategies/**: Strategy interfaces and implementations (e.g., equal weight, fixed weight, mean-variance).
- **models/**: Data models for experiments, backtests, market configs, signals, and solutions.
- **reporting/**: Reporting and output formatting modules.
- **services/**: Factories and builders for optimizers, strategies, and rebalance problems.
- **simulation/**: Backtesting engine and market state simulation.
- **utils/**: Utility functions for lookback windows, rebalance steps, etc.

## Example Workflow

### 1. Experiment Setup

Configure your experiment in a JSON file (e.g., `config/experiment_config.json`).

### 2. Running an Experiment

```python
from application.experiment_runner import ExperimentRunner

runner = ExperimentRunner(config_path="config/experiment_config.json")
runner.run()
```

### 3. Building a Rebalance Problem

```python
from services.rebalance_problem_builder import RebalanceProblemBuilder

builder = RebalanceProblemBuilder(config)
rebalance_problem = builder.build()
```

### 4. Configuring a Strategy

```python
from services.strategy_factory import get_strategy
from services.optimizer_factory import get_optimizer

optimizer = get_optimizer("mean_variance")
strategy = get_strategy("mean_variance", rebalance_problem, optimizer)

# On each rebalance date the strategy:
#   1. Receives signals (mean returns, covariance) from the Signals object
#   2. Calls optimizer.optimize(rebalance_problem, signals, current_weights)
#   3. Applies post-optimisation rules (e.g. vol targeting, cash residual)
#   4. Returns a new np.ndarray of portfolio weights
new_weights = strategy.rebalance(signals, current_weights)
```

### 5. Backtesting

```python
from simulation.backtesting_engine import BacktestingEngine

engine = BacktestingEngine()
results = engine.run_backtest(strategy, market_data)
```

### 6. Reporting

```python
from reporting.reporting_module import generate_report

generate_report(results)
```

## Adding a New Strategy or Optimizer

- Implement your strategy in `domain/strategies/` or optimizer in `domain/optimizers/`.
- Register it in the appropriate factory in `services/`.
- Use interfaces (`istrategy.py`, `ioptimizer.py`) for consistency.

## Project Conventions

- **Modular design:** Each component lives in its own folder.
- **Pure data models:** No business logic in models; calculations in builders/services.
- **Absolute imports:** Always import from the `src` root.
- **Extensible:** Add new strategies, optimizers, or reporting modules easily.

## Dependencies

- Python 3.8+
- CVXPY (for optimization)
- See `requirements.txt` for full list

**Setup:**
   - Create and activate a virtualenv in root: `.venv/`
   - Install dependencies: `pip install -r requirements.txt`

**Run:**
   - Entry point: [src/main.py](src/main.py)
   - Typical pattern: build config dict → use `RebalanceProblemBuilder` → pass to optimizer layer → pass to problem and optimizer to strategy layer → run backtest.
   - Example:
      ```python
      builder = RebalanceProblemBuilder(config)
      problem = builder.build()
      portfolio = Portfolio(...)  # Create portfolio instance
      optimizer = MyOptimizer()  # Initialize optimizer (problem passed to optimize(), not __init__)
      strategy = MyStrategy(optimizer)  # Initialize strategy with optimizer
      signals = SignalsConfig(...)  # Define signals configuration
      weights = strategy.rebalance(signals, portfolio.weights.iloc[current_date])  # Strategy returns new portfolio weights (e.g., np.ndarray)
      ```

**Adding a strategy:**
   - Create a new class in `src/domain/strategies/`, inheriting from a base strategy interface.
   - Implement the `rebalance()` method by passing signals and the current portfolio.
   - Integrate with the workflow above.

**Adding an optimizer:**
   - Create a new class in `src/domain/optimizers/`, implement class inheriting `IOptimizer`.
   - Register in `optimizer_factory._optimizers`.

**Data ingestion:**
   - Update both `marketdatagateway.py` and `RebalanceProblemBuilder` if changing data sources or formats.
   - Builders expect cleaned numpy arrays for all statistics.

---

# Running the UI (Frontend & Backend)

## Backend
1. Create and activate your virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Navigate to `src/` and start the backend server:
   ```bash
   uvicorn main:app --reload
   ```

## Frontend
1. Navigate to the frontend directory.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. The frontend runs on `http://localhost:5173` by default.

## Accessing the App
Open `http://localhost:5173` in your browser. Ensure the backend is running for full functionality.