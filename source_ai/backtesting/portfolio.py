from models.rebalance_solution import RebalanceSubSolution

class Portfolio:
    def __init__(self, optimizer=None):
        self.optimizer = optimizer
    def get_rebalance_solution(self, rebalance_problem):
        if self.optimizer is None:
            return RebalanceSubSolution(
                total_trades=[0.0] * len(rebalance_problem.tickers),
                portfolio_weights=rebalance_problem.initial_weights)
        return self.optimizer.optimize(rebalance_problem)
