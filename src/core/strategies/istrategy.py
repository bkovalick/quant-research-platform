import abc

class StrategyInterface(abc.ABC):
    """Interface for strategy classes."""
    @abc.abstractmethod
    def calculate_drifted_weights(self, prev_weights, prev_asset_returns):
        pass

    @abc.abstractmethod
    def calculate_rebalanced_weights(self, rebalance_idx, lookback_prices):
        pass