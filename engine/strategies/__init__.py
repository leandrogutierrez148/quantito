# Import built-in strategies to trigger their registration decorators
from engine.strategies.base import BaseStrategy
from engine.strategies.fifty_day_avg import FiftyDayAverageStrategy
from engine.strategies.price_momentum import PriceMomentumStrategy
from engine.strategies.registry import StrategyRegistry

__all__ = [
    "BaseStrategy",
    "FiftyDayAverageStrategy",
    "PriceMomentumStrategy",
    "StrategyRegistry",
]
