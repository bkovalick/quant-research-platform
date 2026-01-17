# Portfolio Optimizer - Complete System Architecture

## High-Level System Architecture

```mermaid
graph TB
    subgraph Main["main.py<br/>(Entry Point)"]
        M["Initialize Config<br/>Run Application"]
    end
    
    subgraph Build["Build Phase"]
        Builder["RebalanceProblemBuilder"]
        Gateway["MarketDataGateway<br/>(Infrastructure)"]
        PortCalc["PortfolioCalculations<br/>(Domain Utilities)"]
        Problem["RebalanceProblem<br/>(Data Model)"]
    end
    
    subgraph Optimize["Optimize Phase"]
        Factory["OptimizerFactory"]
        IOptimizer["IOptimizer<br/>(Abstract)"]
        MaxSharpe["MaximizeSharpeOptimizer"]
        MeanVar["MeanVarianceOptimizer"]
        Solution["RebalanceSolution<br/>(Result Model)"]
    end
    
    subgraph Backtest["Backtest Phase"]
        BEngine["BacktestingEngine<br/>(Interface)"]
        BImpl["BacktestingEngine<br/>(Implementation)"]
        Metrics["Performance Metrics"]
    end
    
    M -->|1. Build| Builder
    Builder -->|fetch market data| Gateway
    Builder -->|transform & extract| PortCalc
    Builder -->|create| Problem
    
    M -->|2. Optimize| Factory
    Factory -->|create| IOptimizer
    IOptimizer -->|implements| MaxSharpe
    IOptimizer -->|implements| MeanVar
    MaxSharpe -->|process| Problem
    MeanVar -->|process| Problem
    MaxSharpe -->|produce| Solution
    MeanVar -->|produce| Solution
    
    M -->|3. Backtest| BEngine
    BEngine -->|implements| BImpl
    BImpl -->|run| Problem
    BImpl -->|calculate| Metrics
    
    style M fill:#fff4e6
    style Build fill:#e6f3ff
    style Optimize fill:#e6ffe6
    style Backtest fill:#ffe6f3
```

## Detailed Module Architecture

```mermaid
graph LR
    subgraph Infrastructure["Infrastructure Layer<br/>(External Systems)"]
        Gateway["MarketDataGateway<br/>├─ get_price_data<br/>└─ Uses: yfinance"]
    end
    
    subgraph Portfolio["Portfolio Domain<br/>(src/portfolio/)"]
        Problem["RebalanceProblem<br/>├─ tickers<br/>├─ price_data ⚙️ REACTIVE<br/>├─ returns_data 💾<br/>├─ mean_vector 💾<br/>├─ covariance_matrix 💾<br/>├─ risk_free_rate<br/>├─ target_weights<br/>└─ initial_holdings"]
        
        Builder["RebalanceProblemBuilder<br/>├─ Fetch market data<br/>├─ Transform returns<br/>├─ Calculate statistics<br/>├─ Extract parameters<br/>└─ Build RebalanceProblem"]
        
        Calc["PortfolioCalculations<br/>├─ calculate_returns<br/>├─ calculate_mean_returns<br/>├─ calculate_covariance_matrix<br/>├─ extract_tickers<br/>├─ extract_target_weights<br/>└─ extract_initial_holdings"]
    end
    
    subgraph Optimization["Optimization Layer<br/>(src/core/optimizers/)"]
        IOptimizer["IOptimizer<br/>(Abstract Base)"]
        
        MaxSharpe["MaximizeSharpeOptimizer<br/>├─ MOSEK Model<br/>├─ Variable: y<br/>├─ Constraint: adjusted returns<br/>└─ Objective: minimize variance"]
        
        MeanVar["MeanVarianceOptimizer<br/>├─ Efficient frontier<br/>└─ Placeholder"]
        
        DecisionVars["DecisionVariables<br/>├─ Portfolio weights<br/>└─ Auxiliary variables"]
        
        Factory["OptimizerFactory<br/>├─ maximize_sharpe<br/>└─ mean_variance"]
    end
    
    subgraph Models["Data Models<br/>(src/models/)"]
        Solution["RebalanceSolution<br/>├─ total_trades<br/>└─ target_weights"]
    end
    
    subgraph Backtesting["Backtesting Layer<br/>(src/backtesting/)"]
        BInterface["BacktestingEngineInterface"]
        BEngine["BacktestingEngine<br/>├─ run_backtest<br/>├─ _prepare_portfolio_data<br/>└─ _calculate_performance_metrics"]
    end
    
    Gateway -->|provides| Builder
    Builder -->|uses| Calc
    Builder -->|creates| Problem
    Calc -->|computes| Problem
    
    Problem -->|input to| Factory
    Factory -->|instantiates| IOptimizer
    IOptimizer -->|base of| MaxSharpe
    IOptimizer -->|base of| MeanVar
    MaxSharpe -->|uses| DecisionVars
    MeanVar -->|uses| DecisionVars
    MaxSharpe -->|produces| Solution
    MeanVar -->|produces| Solution
    
    Solution -->|input to| BInterface
    BInterface -->|implements| BEngine
    BEngine -->|analyzes| Problem
    
    style Problem fill:#ffcccc
    style Builder fill:#ccffcc
    style Calc fill:#ccffcc
    style IOptimizer fill:#ffffcc
    style Solution fill:#ffccff
    style BEngine fill:#ccffff
```

## Data Flow: Complete Application Lifecycle

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant Builder
    participant Gateway
    participant Calc as PortfolioCalculations
    participant Problem
    participant Factory
    participant Optimizer
    participant BEngine

    User->>Main: Run with config
    Main->>Builder: Create builder
    Builder->>Gateway: Fetch market data
    Gateway-->>Builder: price_data (DataFrame)
    
    Builder->>Calc: Extract tickers, weights, holdings
    Calc-->>Builder: Config parameters
    
    Builder->>Calc: Calculate returns
    Calc->>Calc: price_data → pct_change()
    Calc-->>Builder: returns_data
    
    Builder->>Calc: Calculate mean & covariance
    Calc-->>Builder: mean_vector, covariance_matrix
    
    Builder->>Problem: Create with prepared_data
    Problem-->>Builder: RebalanceProblem instance
    Builder-->>Main: RebalanceProblem
    
    Main->>Factory: Create optimizer
    Factory-->>Main: Optimizer instance
    
    Main->>Optimizer: optimize(problem)
    Optimizer->>Problem: Access mean_vector
    Problem->>Calc: calculate_mean_returns
    Calc-->>Problem: mean (cached)
    Problem-->>Optimizer: mean_vector
    
    Optimizer->>Problem: Access covariance_matrix
    Problem->>Calc: calculate_covariance_matrix
    Calc-->>Problem: cov (cached)
    Problem-->>Optimizer: covariance_matrix
    
    Optimizer->>Optimizer: Build MOSEK model
    Optimizer->>Optimizer: Solve
    Optimizer-->>Main: RebalanceSolution
    
    Main->>BEngine: run_backtest(problem, optimizer)
    BEngine->>BEngine: Prepare portfolio data
    BEngine->>BEngine: Calculate performance metrics
    BEngine-->>Main: Results
```

## Reactivity Example: Slicing Price Data

```mermaid
sequenceDiagram
    participant User
    participant Problem as RebalanceProblem
    participant Cache as Internal Cache
    participant Calc as PortfolioCalculations

    User->>Problem: Access mean_vector
    alt Cached?
        Problem->>Cache: Check cache
        Cache-->>Problem: Not found
    end
    Problem->>Calc: calculate_returns(price_data)
    Calc-->>Problem: returns_data
    Cache->>Cache: Store returns_data
    
    Problem->>Calc: calculate_mean_returns(returns)
    Calc-->>Problem: mean_vector
    Cache->>Cache: Store mean_vector
    Problem-->>User: mean_vector

    Note over User,Problem: === USER SLICES PRICE DATA ===
    
    User->>Problem: price_data = price_data.tail(60)
    Problem->>Cache: Invalidate returns_data
    Problem->>Cache: Invalidate mean_vector
    Problem->>Cache: Invalidate covariance_matrix
    Cache-->>Problem: Cached values cleared

    Note over User,Problem: === DERIVED PROPERTIES RECOMPUTE ===
    
    User->>Problem: Access mean_vector
    alt Cache cleared, recompute
        Problem->>Calc: calculate_returns(new price_data)
        Calc-->>Problem: NEW returns_data
        Cache->>Cache: Store NEW returns_data
        
        Problem->>Calc: calculate_mean_returns(NEW returns)
        Calc-->>Problem: NEW mean_vector
        Cache->>Cache: Store NEW mean_vector
    end
    Problem-->>User: NEW mean_vector (from 60 days only)
```

## Key Design Patterns

### 1. **Abstract Factory Pattern** (Optimizers)
- `IOptimizer` abstract base class
- `OptimizerFactory` creates concrete implementations
- Enables pluggable optimizer strategies

### 2. **Builder Pattern** (RebalanceProblemBuilder)
- Orchestrates complex object construction
- Separates data fetching, transformation, validation
- Returns fully-prepared `RebalanceProblem`

### 3. **Reactive Properties** (RebalanceProblem)
- `price_data` setter invalidates dependent cached values
- On-demand computation with caching for performance
- Automatic recomputation when data changes

### 4. **Layered Architecture**
- **Infrastructure**: External systems (market data)
- **Portfolio**: Domain logic and data structures
- **Core/Optimizers**: Optimization algorithms (MOSEK)
- **Backtesting**: Performance analysis
- **Models**: Data transfer objects

## Component Dependencies

```mermaid
graph BT
    Main[main.py]
    
    Main -->|uses| Factory[OptimizerFactory]
    Main -->|uses| Builder[RebalanceProblemBuilder]
    
    Builder -->|uses| Gateway[MarketDataGateway]
    Builder -->|uses| Calc[PortfolioCalculations]
    Builder -->|creates| Problem[RebalanceProblem]
    
    Factory -->|creates| Optimizer[Optimizer Instances]
    Optimizer -->|consumes| Problem
    Optimizer -->|produces| Solution[RebalanceSolution]
    
    Backtest[BacktestingEngine] -->|uses| Problem
    Backtest -->|uses| Solution
    
    Calc -->|stateless utilities| none[ ]
    Gateway -->|external API| yfinance["yfinance<br/>(External)"]
    Optimizer -->|external solver| mosek["MOSEK<br/>(External)"]
    
    style Main fill:#fff4e6
    style Problem fill:#ffcccc
    style Solution fill:#ffccff
    style Gateway fill:#ccffff
    style Optimizer fill:#ffffcc
    style yfinance fill:#f0f0f0
    style mosek fill:#f0f0f0
```

## File Organization

```
src/
├── main.py                          # Application entry point
├── config/                          # Configuration (future use)
├── core/
│   └── optimizers/
│       ├── ioptimizer.py           # Abstract base
│       ├── optimizer_factory.py    # Factory pattern
│       ├── maximize_sharp_optimizer/
│       │   ├── maximize_sharpe.py  # MOSEK implementation
│       │   └── decision_variables_max_sharpe.py
│       └── mean_variance_optimizer/
│           └── mean_variance_optimizer.py
├── infrastructure/
│   └── market_data/
│       └── marketdatagateway.py     # yfinance wrapper
├── portfolio/
│   ├── rebalance_problem.py         # Reactive data container
│   ├── rebalance_problem_builder.py # Orchestrator
│   └── portfolio_calculations.py    # Domain utilities
├── models/
│   └── rebalance_solution.py        # Solution model
└── backtesting/
    └── backtesting_engine.py        # Performance analysis
```
