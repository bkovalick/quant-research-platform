import abc

class PortfolioInterface(abc.ABC):
    """Interface for portfolio classes."""
    @abc.abstractmethod
    def initialize(self, rebalance_problem):
        pass