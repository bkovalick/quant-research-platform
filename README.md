# portfolio-optimizer


Portfolio-optimizer is a modular toolkit for portfolio optimization and backtesting, supporting multiple strategies (fixed weights, mean-variance, Sharpe maximization) and designed for extensibility and experimentation. It features a clean separation between market data, portfolio configuration, and optimization logic.

## System Overview
This repository is a modular toolkit for portfolio optimization and backtesting. It supports multiple strategies (fixed weights, mean-variance, Sharpe maximization) and is designed for extensibility and experimentation.


### Architecture
- **Python Core:**
   - Portfolio construction, optimization, and backtesting are implemented in Python.
   - Market data is managed by a MarketEnvironment class, which is configured independently of portfolio logic and provides normalized prices and all derived statistics (returns, covariance, mean vector) as properties. These statistics always reflect the current normalized prices.
   - A cash column (all 1s) is automatically added to price data, and a cash component is included in all portfolios with a starting weight of 0.
   - Strategies are defined via configuration and run through a unified pipeline.
   - Results are returned as pandas DataFrames and scalars for reporting and analysis.
- **C++ Parallel Runner:**
   - A C++ wrapper (using pybind11) can launch multiple Python strategy runs in parallel, enabling fast grid search or batch evaluation.
   - The C++ runner calls a Python entry point (`src/strategy_runner.py`) for each strategy/configuration.

### Workflow
1. **Data Preparation:**
   - Market data is ingested and cleaned via MarketEnvironment, which fetches, normalizes, and exposes all statistics as properties.
   - Portfolio statistics (mean, covariance, etc.) are always computed from the current normalized prices, and update automatically if normalized_prices is changed.
   - A cash asset is always present in the data and portfolios.
2. **Strategy Configuration:**
   - Strategies are specified via config dictionaries (tickers, weights, risk parameters, etc.).
3. **Optimization & Backtesting:**
   - The optimizer is selected and run for each strategy.
   - The backtesting engine simulates portfolio evolution over time, applying rebalancing logic.
4. **Reporting:**
   - Results (returns, weights, turnover, drawdown, etc.) are collected and exported for analysis.
   - Optional: C++ runner aggregates results from parallel strategy runs.


### Extensibility
- Add new strategies by implementing an optimizer and registering it in the factory.
- Integrate with other languages or systems via the Python entry point and C++ wrapper.
- Output is designed for easy reporting, visualization, and further research.
- MarketEnvironment and portfolio logic are decoupled, so you can reuse the same data for multiple strategies or rebalancing problems.

## C++ Parallel Strategy Runner

This project supports running Python strategies in parallel from C++ using pybind11.

### Requirements
- Python 3.x (with all required packages: pandas, numpy, PyYAML, etc.)
- pybind11 (install via pip: `pip install pybind11` or use your package manager)
- CMake >= 3.14
- C++17 compiler (MSVC, g++, clang++)

### Build Instructions
1. Open a terminal in the project root.
2. Run:
   ```sh
   mkdir build
   cd build
   cmake ..
   cmake --build .
   ```
   This will produce `cpp_strategy_runner.exe` (Windows) or `cpp_strategy_runner` (Linux/Mac) in the build directory.

### Run Instructions
1. Ensure your Python environment is activated and `src/` is in your `PYTHONPATH`.
2. Run the executable:
   ```sh
   ./cpp_strategy_runner
   ```
   The program will launch the Python interpreter, feed strategies, and print results in parallel.


### Troubleshooting
- If you get import errors, ensure `src/` is in `PYTHONPATH` and all Python dependencies are installed.
- You may need to adjust the `CMakeLists.txt` or environment variables if Python or pybind11 are not found automatically.
- If portfolio statistics do not update as expected, check that you are accessing them via MarketEnvironment properties and that normalized_prices is up to date.

See `cpp_strategy_runner.cpp` and `src/strategy_runner.py` for example usage and integration details.

