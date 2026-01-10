import pandas as pd
import numpy as np

import config as cfg
from data import rebalance_problem


if __name__ == '__main__':
    rebal_problem = {}
    rebal_problem["mu"] = returns_array = np.array([
        [0.01, 0.02, 0.03],
        [0.02, 0.01, 0.04],
        [-0.01, 0.00, 0.01],
        [0.03, -0.01, 0.02]
    ])
    rebal_problem["covMatrix"] = np.cov(rebal_problem["mu"], rowvar = False)
    rebal_problem["riskFreeRate"] = 0.03
    print(rebal_problem["covMatrix"])