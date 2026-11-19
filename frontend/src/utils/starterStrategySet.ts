import type { StrategySet } from "./mergeStrategySets"

// A small, liquid, multi-asset universe so the starter runs quickly and is always feasible.
const STARTER_TICKERS = ["SPY", "IWM", "EFA", "EEM", "AGG", "TLT", "LQD", "HYG", "GLD", "VNQ"]

/**
 * A strategy set to start from when no JSON is loaded: one mean-variance strategy on a
 * handful of ETFs. Everything in it can be changed in the Strategy Lab. Dates, benchmark,
 * transaction cost and risk-free rate come from the Experiment tab's fields at run time.
 */
export function starterStrategySet(): StrategySet {
  return {
    database_name: "research.duckdb",
    market_store_config: {
      data_source: { yfinance: null },
      apply_market_caps: false,
      // Needed for the "Point-in-time S&P 500 members" switch in the Lab.
      historical_sp500_tickers_path: "data/S&P 500 Historical Components & Changes.csv",
      tickers: [...STARTER_TICKERS],
    },
    strategies: [
      {
        name: "custom_strategy_1",
        market_state_config: {
          lookback_window_key: "1y",
          market_frequency: "d",
          cash_allocation: 0.005,
          exogenous_tickers: [],
          investment_universe: [...STARTER_TICKERS],
          include_sp500_members: false,
        },
        signals_config: {
          apply_winsorizing: true,
          windsor_percentiles: { lower: 0.05, upper: 0.95 },
        },
        rebalance_problem: {
          strategy_type: "systematic_strategy",
          signal_source: "risk_return",
          optimizer_type: "parameterized_optimizer",
          rebalance_frequency: "weekly",
          apply_tax_objective: false,
          constraints: {
            concentration_strength: 1,
            risk_aversion: 1.0,
            turnover_limit: 1.0,
            min_position_size: 0.0,
            max_position_size: 0.35,
          },
        },
      },
    ],
  }
}
