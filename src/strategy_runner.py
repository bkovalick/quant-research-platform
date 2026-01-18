import json
from core.optimizers.optimizer_factory import OptimizerFactory
from portfolio.portfolio import Portfolio
from portfolio.rebalance_problem_builder import RebalanceProblemBuilder
from backtesting.backtesting_engine import BacktestingEngine

def run_strategy(config):
    """Run a single strategy and return results as JSON-serializable dict."""
    builder = RebalanceProblemBuilder(config)
    rebalance_problem = builder.build()
    optimizer = OptimizerFactory.create_optimizer(config["program_type"])
    portfolio = Portfolio(optimizer=optimizer)
    backtestingEngine = BacktestingEngine(portfolio)
    metrics = backtestingEngine.run_backtest(rebalance_problem)
    # Convert all results to JSON-serializable (e.g., convert DataFrames to dict)
    result = {k: (v.to_dict() if hasattr(v, 'to_dict') else v) for k, v in metrics.items()}
    return result

# Optional: CLI entry point for manual testing
if __name__ == "__main__":
    import sys
    import yaml
    config = yaml.safe_load(open(sys.argv[1]))
    result = run_strategy(config)
    print(json.dumps(result, indent=2))
