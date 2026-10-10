# Import built-in strategies to trigger their registration decorators
from quantito.strategies.base import BaseStrategy
from quantito.strategies.fifty_day_avg import FiftyDayAverageStrategy
from quantito.strategies.price_momentum import PriceMomentumStrategy
from quantito.strategies.registry import StrategyRegistry

__all__ = [
    "BaseStrategy",
    "FiftyDayAverageStrategy",
    "PriceMomentumStrategy",
    "StrategyRegistry",
]
