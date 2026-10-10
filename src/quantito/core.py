import json
import logging
import os
from typing import Any

# Ensure strategies are registered
import quantito.strategies  # noqa: F401
from quantito.models import Signal
from quantito.strategies.base import BaseStrategy
from quantito.strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Core Context and Orchestrator for Strategy Execution.

    Implements the Strategy Pattern:
    - Encapsulates strategy evaluation via polymorphic delegation.
    - Enables hot-swapping strategies at runtime via `set_strategy`.
    """

    def __init__(self, strategy: BaseStrategy):
        self._strategy: BaseStrategy = strategy
        logger.info(f"SignalEngine initialized with Strategy: '{self._strategy.name}'.")

    @property
    def strategy(self) -> BaseStrategy:
        """Get current active strategy."""
        return self._strategy

    def set_strategy(self, strategy: BaseStrategy) -> None:
        """Hot-swap the active strategy at runtime."""
        old_name = self._strategy.name if self._strategy else "None"
        self._strategy = strategy
        logger.info(f"SignalEngine strategy swapped: '{old_name}' -> '{self._strategy.name}'")

    @classmethod
    def from_environment(
        cls,
        default_strategy: str = "fifty_day_avg",
    ) -> "SignalEngine":
        """
        Factory method to configure the engine automatically from environment variables:
        - `STRATEGY_NAME`: Name of the strategy to load (e.g. 'fifty_day_avg', 'price_momentum').
        - `STRATEGY_PARAMS`: JSON string containing strategy keyword arguments.
        """
        strategy_name = os.getenv("STRATEGY_NAME", default_strategy)
        raw_params = os.getenv("STRATEGY_PARAMS", "{}")

        try:
            params = json.loads(raw_params) if raw_params else {}
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse STRATEGY_PARAMS JSON ('{raw_params}'). Using defaults. Error: {e}"
            )
            params = {}

        strategy_instance = StrategyRegistry.create(strategy_name, **params)
        return cls(strategy=strategy_instance)

    def process(self, market_data: list[dict[str, Any]]) -> list[Signal]:
        """
        Evaluate market data records against the active strategy and return results.

        Args:
            market_data: List of quote or candle dictionaries.

        Returns:
            List of generated Signal instances.
        """
        if not market_data:
            logger.debug("SignalEngine.process called with empty market data.")
            return []

        logger.info(
            f"SignalEngine running strategy '{self._strategy.name}' on {len(market_data)} market data item(s)..."
        )

        signals = self._strategy.generate_signals(market_data)
        logger.info(f"SignalEngine generated {len(signals)} signal(s).")
        return signals
