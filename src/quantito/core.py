import json
import logging
import os
from typing import Any

# Ensure strategies are registered
import quantito.strategies  # noqa: F401
from quantito.models import Signal
from quantito.sinks.base import BaseSignalSink
from quantito.sinks.bigquery import BigQuerySignalSink
from quantito.sinks.console import ConsoleSignalSink
from quantito.strategies.base import BaseStrategy
from quantito.strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Core Context and Orchestrator for Signal Generation.

    Implements the Strategy Pattern:
    - Encapsulates strategy evaluation via polymorphic delegation.
    - Enables hot-swapping strategies at runtime via `set_strategy`.
    - Dispatches generated signals across configured sinks (console, BigQuery, webhooks).
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        sinks: list[BaseSignalSink] | None = None,
    ):
        self._strategy: BaseStrategy = strategy
        self._sinks: list[BaseSignalSink] = sinks if sinks is not None else [ConsoleSignalSink()]
        logger.info(
            f"SignalEngine initialized with Strategy: '{self._strategy.name}' and {len(self._sinks)} sink(s)."
        )

    @property
    def strategy(self) -> BaseStrategy:
        """Get current active strategy."""
        return self._strategy

    @property
    def sinks(self) -> list[BaseSignalSink]:
        """Get list of active sinks."""
        return self._sinks

    def set_strategy(self, strategy: BaseStrategy) -> None:
        """
        Hot-swap the active strategy at runtime.
        """
        old_name = self._strategy.name if self._strategy else "None"
        self._strategy = strategy
        logger.info(f"SignalEngine strategy swapped: '{old_name}' -> '{self._strategy.name}'")

    def add_sink(self, sink: BaseSignalSink) -> None:
        """Add an additional output sink."""
        self._sinks.append(sink)

    @classmethod
    def from_environment(
        cls,
        default_strategy: str = "fifty_day_avg",
        include_bigquery: bool = True,
    ) -> "SignalEngine":
        """
        Factory method to configure the engine automatically from environment variables:
        - `STRATEGY_NAME`: Name of the strategy to load (e.g. 'fifty_day_avg', 'price_momentum').
        - `STRATEGY_PARAMS`: JSON string containing strategy keyword arguments.
        - `ENABLE_BQ_SIGNALS`: If 'true'/'1', automatically attaches BigQuerySignalSink.
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

        sinks: list[BaseSignalSink] = [ConsoleSignalSink()]

        # Attach BigQuery sink if enabled and dataset configured
        enable_bq = os.getenv("ENABLE_BQ_SIGNALS", "true").lower() in ("true", "1", "yes")
        if include_bigquery and enable_bq and os.getenv("BIGQUERY_DATASET"):
            sinks.append(BigQuerySignalSink())

        return cls(strategy=strategy_instance, sinks=sinks)

    def process(self, market_data: list[dict[str, Any]]) -> list[Signal]:
        """
        Evaluate market data records against the active strategy and dispatch
        results to all registered sinks.

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

        # Polymorphic execution of active strategy
        signals = self._strategy.generate_signals(market_data)
        logger.info(f"SignalEngine generated {len(signals)} signal(s).")

        # Dispatch signals to all configured sinks
        for sink in self._sinks:
            try:
                sink.send(signals)
            except Exception as e:
                logger.error(f"Error in sink '{type(sink).__name__}': {e}")

        return signals
