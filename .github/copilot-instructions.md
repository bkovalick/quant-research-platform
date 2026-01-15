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
  - Separates concerns: fetching (MarketDataGateway) + transformation (DataProcessor) + encapsulation (RebalanceProblem)
- **DataProcessor**: [src/portfolio/data_processor.py](src/portfolio/data_processor.py)
  - Static utility methods for data transformations (returns, mean, covariance, parameter extraction)

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

## Important Patterns & Conventions

### MOSEK Model Setup Pattern
```python
# In optimizer classes:
from mosek.fusion import *

def optimize(self, rebalance_problem):
    with Model("problem_name") as M:
        # Define decision variables using Domain.*
        y = M.variable("y", n, Domain.greaterThan(0.0))
        
        # Add constraints
        M.constraint("constraint_name", expr, Domain.equalsTo(value))
        
        # Set objective
        M.objective("obj_name", ObjectiveSense.Minimize, expr)
        
        # Solve
        M.solve()
        
        # Retrieve results
        result = y.level()
```

### Financial Optimization Problem Formulation
- **Sharpe Ratio Maximization**: Non-convex by nature → reformulate using variable change
  - Original: `max_x (μ^T*x - rf) / sqrt(x^T*Σ*x)` subject to `Σx_i = 1, x ≥ 0`
  - Transformed: `min_y y^T*Σ*y` subject to `(μ - rf)^T*y = 1, y ≥ 0`
  - Recovery: `x_i = y_i / Σy_j`
- Input data must satisfy: returns array `mu`, covariance matrix `covMatrix`, risk-free rate `rf`

## Common Development Tasks

### Adding a New Optimizer
1. Create `src/core/optimizers/<name>/` directory
2. Create `<name>.py` with class inheriting from `IOptimizer`
3. Implement `optimize(rebalance_problem)` using MOSEK Fusion API
4. Add `__init__.py` in optimizer directory
5. Test in `main.py` before committing

### Implementing MaximizeSharpeOptimizer
- Uncomment the template code in [maximize_sharpe.py](src/core/optimizers/maximize_sharp_optimizer/maximize_sharpe.py) 
- Key variables: `y` decision variables, adjusted returns constraint, quadratic objective
- After solving: transform `y_optimal` back to portfolio weights `x`
- Validate with: `sharpe_ratio = (μ^T*x - rf) / sqrt(x^T*Σ*x)`

### Debugging MOSEK Models
- Check if `Model.solve()` completes without exception
- Access solution values via `.level()` on decision variables
- MOSEK reports status through model attributes (check documentation for return codes)

## File Organization Summary
```
src/
├── main.py                          # Entry point
├── config/                          # Config module (empty, for future use)
├── core/
│   └── optimizers/
│       ├── ioptimizer.py           # Abstract base class
│       ├── maximize_sharp_optimizer/
│       │   ├── maximize_sharpe.py   # Main optimizer (template code available)
│       │   └── decision_variables_max_sharpe.py
│       └── mean_variance_optimizer/
│           └── mean_variance_optimizer.py  # Placeholder for efficient frontier
├── infrastructure/
│   └── market_data/
│       └── marketdatagateway.py     # Fetches market data via yfinance
└── portfolio/
    ├── rebalance_problem.py         # Pure data container
    ├── rebalance_problem_builder.py # Orchestrates data pipeline
    └── data_processor.py            # Transformation utilities
```

## Critical Notes for AI Agents
- **Status**: Active experimentation repo with partial implementations
- **Architecture**: Clean separation - `RebalanceProblemBuilder` orchestrates pipeline → `RebalanceProblem` holds clean data → optimizers consume data
- **MaximizeSharpeOptimizer**: Template code commented out - ready to be uncommented and tested
- **Optimizer interface**: `optimize(rebalance_problem: RebalanceProblem)` receives clean data, accesses via properties
- **Data properties** on `RebalanceProblem`: Use `problem.mean_vector`, `problem.covariance_matrix`, etc. (not `get_*` methods)
- **MOSEK API**: Always use `with Model() as M:` context manager; use `Domain.*`, `Expr.*`, `Matrix.*` for problem construction
- **Financial validation**: Implement tests to verify optimized Sharpe ratio calculation matches portfolio theory
