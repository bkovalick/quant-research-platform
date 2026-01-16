import abc

class BacktestingEngineInterface(abc.ABC):
    """Interface for backtesting engines."""
    @abc.abstractmethod
    def run_backtest(self, rebalance_problem, optimizer):
        pass

class BacktestingEngine(BacktestingEngineInterface):
    def __init__(self, rebalance_problem):
        super().__init__()
        self.rebalance_problem = rebalance_problem
        self.prices = self.rebalance_problem.price_data

    """Concrete implementation of a backtesting engine."""
    def run_backtest(self, rebalance_problem, optimizer):
        # Placeholder for backtesting logic
        print("Running backtest...")
        for i, date in enumerate(self.prices.index):
            input_return_data = self.prices.loc[:date]
            # Update portfolio state
            rebalance_solution = optimizer.optimize(rebalance_problem)

            # Collect and analyze results
            self._prepare_portfolio_data(rebalance_problem, rebalance_solution)

        print("Backtest completed.")


    def _prepare_portfolio_data(self, rebalance_problem, rebalance_solution):
        # Placeholder for preparing portfolio statistics
        pass

    def _calculate_performance_metrics(self):
        # Placeholder for calculating performance metrics
        # cumulative returns, volatility, Sharpe ratio, max drawdown, turnovers, etc.
        pass