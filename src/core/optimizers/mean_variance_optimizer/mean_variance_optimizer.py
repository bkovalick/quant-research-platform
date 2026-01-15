from mosek.fusion import *
import numpy as np

from core.optimizers.ioptimizer import IOptimizer
from portfolio.rebalance_problem import RebalanceProblem

class MeanVarianceOptrimizer(IOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, rebalance_problem: RebalanceProblem):
        self.output_efficient_frontier(rebalance_problem)

    def output_efficient_frontier(self, rebalance_problem: RebalanceProblem):
        pass