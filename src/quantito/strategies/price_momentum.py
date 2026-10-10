import datetime
from typing import Any

from quantito.models import Signal, SignalType
from quantito.strategies.base import BaseStrategy
from quantito.strategies.registry import StrategyRegistry


@StrategyRegistry.register("price_momentum")
class PriceMomentumStrategy(BaseStrategy):
    """
    Evaluates intraday or periodic price changes against threshold percentages.
    Useful for real-time and delayed quotes with 'change_p' or 'change'.
    """

    def __init__(
        self,
        min_change_pct: float = 1.5,
        **kwargs: Any,
    ):
        super().__init__(min_change_pct=min_change_pct, **kwargs)
        self.min_change_pct = float(min_change_pct)

    @property
    def name(self) -> str:
        return "price_momentum"

    def generate_signals(self, market_data: list[dict[str, Any]]) -> list[Signal]:
        signals: list[Signal] = []
        now = datetime.datetime.now(datetime.UTC)

        for row in market_data:
            if not isinstance(row, dict):
                continue

            symbol = row.get("code") or row.get("symbol")
            price = row.get("close") or row.get("lastTradePrice")
            change_p = row.get("change_p")

            if not symbol or price is None or change_p is None:
                continue

            try:
                price = float(price)
                change_p = float(change_p)
            except (ValueError, TypeError):
                continue

            if change_p >= self.min_change_pct:
                confidence = min(1.0, max(0.1, abs(change_p) / 5.0))
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        price=price,
                        timestamp=now,
                        strategy_name=self.name,
                        confidence=confidence,
                        metadata={
                            "change_pct": round(change_p, 4),
                            "min_change_pct": self.min_change_pct,
                        },
                    )
                )
            elif change_p <= -self.min_change_pct:
                confidence = min(1.0, max(0.1, abs(change_p) / 5.0))
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        price=price,
                        timestamp=now,
                        strategy_name=self.name,
                        confidence=confidence,
                        metadata={
                            "change_pct": round(change_p, 4),
                            "min_change_pct": self.min_change_pct,
                        },
                    )
                )

        return signals
