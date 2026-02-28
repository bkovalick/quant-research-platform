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
│   ├── experiment_20260220.json
├── data/
│   ├── market_data_gateway.py
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
- **data/**: Handles market data ingestion and metadata management.
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

Configure your experiment in a JSON file (e.g., `config/experiment_20260220.json`).

### 2. Running an Experiment

```python
from application.experiment_runner import ExperimentRunner

runner = ExperimentRunner(config_path="config/experiment_20260220.json")
runner.run()
```

### 3. Building a Rebalance Problem

```python
from services.rebalance_problem_builder import RebalanceProblemBuilder

builder = RebalanceProblemBuilder(config)
rebalance_problem = builder.build()
```

### 4. Optimizing a Portfolio

```python
from services.optimizer_factory import get_optimizer

optimizer = get_optimizer("mean_variance")
solution = optimizer.optimize(rebalance_problem)
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

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## License

See CVXPY and other library documentation for licensing.

---

For more details, see the source code and configuration files in the `src/` directory.