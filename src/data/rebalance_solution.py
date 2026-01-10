from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import Union

@dataclass
class RebalanceSolution:
    """
    Data class representing a rebalanced portfolio
    """

    target_weights: Union[np.ndarray, pd.Series]
