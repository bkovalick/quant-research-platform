from functools import cached_property

class RebalanceProblem:
    def __init__(self, body):
        self.body = body
        self.mu = body["mu"]
        self.covMatrix = body["covMatrix"]

    @cached_property
    def n_constituents(self):
        return len(self.get_return_series)

    @cached_property
    def get_return_series(self):
        return self.mu

    @cached_property
    def get_covariance_matrix(self):
        return self.covMatrix
    
    @cached_property
    def get_risk_free_rate(self):
        return 0.02