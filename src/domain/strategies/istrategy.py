import abc

class StrategyInterface(abc.ABC):
    """Interface for strategy classes."""
    @abc.abstractmethod
    def rebalance(self, signals, current_weights):
        raise NotImplementedError("Derived classes must implement 'rebalance' method")