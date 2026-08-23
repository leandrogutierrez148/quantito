from abc import ABC, abstractmethod
from typing import Any

from engine.models import Signal


class BaseStrategy(ABC):
    """
    Abstract Strategy Contract.
    All concrete trading strategies must inherit from this class and implement generate_signals.
    """

    def __init__(self, **params: Any):
        self.params = params

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name for this strategy."""

    @property
    def description(self) -> str:
        """Human-readable description of what the strategy does."""
        return self.__doc__ or ""

    @abstractmethod
    def generate_signals(self, market_data: list[dict[str, Any]]) -> list[Signal]:
        """
        Evaluate market data records and generate zero or more trading signals.

        Args:
            market_data: List of quote or bar dictionaries (e.g. from EODHD delayed, real_time, eod).

        Returns:
            List of generated Signal instances.
        """
