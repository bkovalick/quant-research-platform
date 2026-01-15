from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import Union
from mosek.fusion import *

from core.optimizers.maximize_sharp_optimizer.decision_variables_max_sharpe import MaximizeSharpeDecisionVariables

class RebalanceSolution:
    """
    Class representing the solution to a rebalance optimization problem
    """
    def __init__(self, 
                 model,
                 decision_variables: MaximizeSharpeDecisionVariables):
        self.model = model
        self.decision_variables = decision_variables

    def get_rebalance_solution(self) -> 'RebalanceSubSolution':
        return RebalanceSubSolution(
            total_trades=self.decision_variables.total_trades.level(),
            target_weights=self.decision_variables.x.level()
        )

@dataclass
class RebalanceSubSolution:
    """
    Data class representing a rebalanced portfolio solution
    """

    total_trades: Union[np.ndarray, pd.Series]
    target_weights: Union[np.ndarray, pd.Series]
