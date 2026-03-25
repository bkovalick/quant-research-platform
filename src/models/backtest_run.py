from dataclasses import dataclass, field
from domain.portfolio.iportfolio import PortfolioInterface

@dataclass
class BacktestRun:
    portfolio: PortfolioInterface
    scores_history: dict = field(default_factory=dict)
    fwd_returns_history: dict = field(default_factory=dict)
