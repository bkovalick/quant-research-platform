from mosek.fusion import *
from portfolio.rebalance_problem import RebalanceProblem

class MaximizeSharpeDecisionVariables:
    def __init__(self, 
                 model, 
                 rebalance_problem: RebalanceProblem):
        n_constituents = rebalance_problem.n_constituents
        self.portfolio_weights = model.variable("portfolio_weights", n_constituents, Domain.greaterThan(0.0))
        self.total_trades = model.variable("total_trades", n_constituents, Domain.unbounded())