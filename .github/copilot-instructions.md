# Copilot Instructions for gurobi-examples

## Project Overview
This is an experimentation repository for building financial optimization problems using Gurobi's Python API. The project uses object-oriented design patterns to implement modular optimization solvers, starting with portfolio optimization (Sharpe ratio maximization).

## Architecture & Component Structure

### Core Design Pattern: Abstract Optimizer Interface
- **File**: `src/gurobi_examples.optimizers/ioptimizer.py`
- All optimizers implement the `IOptimizer` abstract base class with a single `optimize(rebalance_problem)` method
- This pattern enables pluggable optimizer implementations for different problem types

### Optimizer Implementations
- **Location**: `src/gurobi_examples.optimizers/<optimizer_name>/`
- Each optimizer gets its own subdirectory with:
  - `<optimizer_name>.py` - main optimizer class inheriting from `IOptimizer`
  - `decision_variables_<optimizer_name>.py` - encapsulates Gurobi decision variable initialization
  - `__init__.py` - package initialization

### Example: MaximizeSharpe Optimizer
- **Files**: 
  - `maximize_sharpe.py` - `MaximizeSharpeOptimizer` class implementing portfolio weight optimization
  - `decision_variables_max_sharpe.py` - `MaximizeSharpeDecisionVariables` class for portfolio weights and auxiliary variables
- **Pattern**: Separate decision variable setup from model logic for maintainability
- **Gurobi Variables Used**:
  - Portfolio weights (0-1 bounds, sum to 1 constraint expected)
  - Auxiliary variable `y` for Sharpe ratio denominator transformation

## Key Technologies & Dependencies
- **gurobipy 13.0.0** - Commercial optimization solver (requires license, free tier available)
- **gurobipy-pandas 1.1.1** - Pandas integration for easier data handling
- **pandas 2.3.3** - Data manipulation and financial data loading
- **numpy 1.26.4** - Numerical computations
- **yfinance 0.2.38** - Fetch market data for portfolio optimization
- **scikit-learn, statsmodels** - Statistical analysis and model building

## Developer Workflows

### Environment Setup
1. Create virtual environment: `.venv/` directory in root (already present)
2. Install dependencies: `pip install -r requirements.txt`
3. **Known Issue**: Gurobi requires license setup - free tier available for non-commercial use

### Running Code
- Entry point: `src/main.py` (currently minimal)
- Add new optimizer experiments to `main()` function
- Use imports like: `from gurobi_examples.optimizers.maximize_sharpe.maximize_sharpe import MaximizeSharpeOptimizer`

### Module Structure
- Package naming: `gurobi_examples.optimizers.<optimizer_type>`
- All subdirectories contain `__init__.py` to ensure proper Python package recognition
- Import relative modules carefully: `maximize_sharpe.py` imports `ioptimizer` (not fully qualified path)

## Important Patterns & Conventions

### Gurobi Model Setup Pattern
```python
# In optimizer classes:
self.model = gp.Model("ProblemName")
# Define variables, objective, constraints
# Call self.model.optimize()
# Check status with: if self.model.status == gp.GRB.OPTIMAL
```

### Decision Variables Pattern
- Create a separate class per optimizer for decision variable encapsulation
- Use `gp.AddVars()` for arrays of variables (indexed)
- Use `gp.AddVar()` for scalar variables
- Specify bounds (lb, ub) and names for clarity during debugging

### Incomplete Implementations
- Current code has placeholder methods: `get_decision_variables()`, `get_model_constraints()`, `set_model_objective()`
- These should be fleshed out as the optimizer is developed
- Decision variables should be extracted and returned for solution analysis

## Common Development Tasks

### Adding a New Optimizer
1. Create `src/gurobi_examples.optimizers/<name>/` directory
2. Create `<name>.py` with class inheriting from `IOptimizer`
3. Create `decision_variables_<name>.py` for variable setup
4. Create `__init__.py` in both locations
5. Test in `main.py` before committing

### Debugging Gurobi Models
- Check `self.model.status` after optimization (should equal `gp.GRB.OPTIMAL`)
- Review objective value: `self.model.objVal`
- Print variable values: `var.X` attribute contains optimized values
- Use `model.write()` to export .lp or .sol files for inspection

### Financial Domain Notes
- Portfolio optimization typically constraints: sum of weights = 1, weights non-negative
- Sharpe ratio = (return - risk_free_rate) / std_dev - requires careful algebraic transformation for solver
- Returns and covariance matrices needed as inputs to `optimize()` method

## File Organization Summary
```
src/
├── main.py                          # Entry point
├── gurobi_examples.config/          # Config module (empty, for future use)
└── gurobi_examples.optimizers/
    ├── ioptimizer.py               # Abstract base class
    └── maximize_sharpe/            # Portfolio optimization
        ├── maximize_sharpe.py       # Main optimizer
        └── decision_variables_max_sharpe.py  # Gurobi variables
```

## Notes for AI Agents
- This is an active experimentation repo with incomplete implementations
- Focus on following established patterns when adding features
- Gurobi models require careful mathematical formulation - review constraints and objective transformation
- Financial calculations need validation against expected portfolio theory results
- The license-based nature of Gurobi means some tests may fail without proper setup
