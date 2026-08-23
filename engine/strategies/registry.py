import logging
from collections.abc import Callable
from typing import Any, ClassVar

from engine.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Registry and Factory for Strategy implementations.
    Allows registering strategies with @StrategyRegistry.register("name")
    and dynamic instantiation via StrategyRegistry.create("name", **params).
    """

    _strategies: ClassVar[dict[str, type[BaseStrategy]]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[BaseStrategy]], type[BaseStrategy]]:
        """
        Decorator to register a Strategy class under a given name.
        """

        def decorator(subclass: type[BaseStrategy]) -> type[BaseStrategy]:
            key = name.strip().lower()
            if key in cls._strategies:
                logger.warning(f"Overwriting existing strategy registration for: '{key}'")
            cls._strategies[key] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, name: str, **params: Any) -> BaseStrategy:
        """
        Instantiate a registered strategy by name with parameter overrides.
        """
        key = name.strip().lower()
        if key not in cls._strategies:
            available = cls.list_strategies()
            raise ValueError(f"Unknown strategy: '{name}'. Available strategies: {available}")
        strategy_cls = cls._strategies[key]
        logger.info(f"Instantiating strategy '{key}' with parameters: {params}")
        return strategy_cls(**params)

    @classmethod
    def list_strategies(cls) -> list[str]:
        """Return list of all registered strategy names."""
        return sorted(cls._strategies.keys())

    @classmethod
    def get_strategy_class(cls, name: str) -> type[BaseStrategy]:
        """Retrieve strategy class without instantiating."""
        key = name.strip().lower()
        if key not in cls._strategies:
            raise ValueError(f"Unknown strategy: '{name}'")
        return cls._strategies[key]
