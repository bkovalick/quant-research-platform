from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import Union
from mosek.fusion import *

class RebalanceSolution:
    """
    Class representing the solution to a rebalance optimization problem
    """
    def __init__(self, 
                 model,
                 decision_variables,
                 rebalance_problem):
        self.model = model
        self.decision_variables = decision_variables
        self.rebalance_problem = rebalance_problem
        self.rebalance_sub_solution = self.get_rebalance_sub_solution()

    def get_rebalance_sub_solution(self) -> 'RebalanceSubSolution':
        return RebalanceSubSolution(
            total_trades=self.decision_variables['total_trades'],
            portfolio_weights=self.decision_variables['portfolio_weights']
        )

@dataclass
class RebalanceSubSolution:
    """
    Data class representing a rebalanced portfolio solution
    """

    total_trades: Union[np.ndarray, pd.Series]
    portfolio_weights: Union[np.ndarray, pd.Series]
