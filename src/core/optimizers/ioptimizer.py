import abc

class IOptimizer(abc.ABC):
    @abc.abstractmethod
    def optimize(self, rebalance_problem, current_weights=None):
        pass