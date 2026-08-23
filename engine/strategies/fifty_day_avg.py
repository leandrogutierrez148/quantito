import datetime
from typing import Any

from engine.models import Signal, SignalType
from engine.strategies.base import BaseStrategy
from engine.strategies.registry import StrategyRegistry


@StrategyRegistry.register("fifty_day_avg")
class FiftyDayAverageStrategy(BaseStrategy):
    """
    Evaluates quotes against their 50-day average price.
    Generates BUY signals when the price is above the average by at least threshold_pct %,
    or SELL signals when below by threshold_pct %.
    """

    def __init__(
        self,
        threshold_pct: float = 0.0,
        signal_on: str = "above",  # "above", "below", or "both"
        **kwargs: Any,
    ):
        super().__init__(threshold_pct=threshold_pct, signal_on=signal_on, **kwargs)
        self.threshold_pct = float(threshold_pct)
        self.signal_on = signal_on.lower()

    @property
    def name(self) -> str:
        return "fifty_day_avg"

    def generate_signals(self, market_data: list[dict[str, Any]]) -> list[Signal]:
        signals: list[Signal] = []
        now = datetime.datetime.now(datetime.UTC)

        for row in market_data:
            if not isinstance(row, dict):
                continue

            symbol = row.get("symbol") or row.get("code")
            last_price = row.get("lastTradePrice") or row.get("close")
            avg_50 = row.get("fiftyDayAveragePrice")

            if not symbol or last_price is None or avg_50 is None:
                continue

            try:
                last_price = float(last_price)
                avg_50 = float(avg_50)
            except (ValueError, TypeError):
                continue

            if avg_50 == 0:
                continue

            diff_pct = ((last_price - avg_50) / avg_50) * 100.0

            if self.signal_on in ("above", "both") and diff_pct > self.threshold_pct:
                confidence = min(1.0, max(0.1, abs(diff_pct) / 10.0))
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        price=last_price,
                        timestamp=now,
                        strategy_name=self.name,
                        confidence=confidence,
                        metadata={
                            "fiftyDayAveragePrice": avg_50,
                            "diff_pct": round(diff_pct, 4),
                            "threshold_pct": self.threshold_pct,
                        },
                    )
                )
            elif self.signal_on in ("below", "both") and diff_pct < -self.threshold_pct:
                confidence = min(1.0, max(0.1, abs(diff_pct) / 10.0))
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        price=last_price,
                        timestamp=now,
                        strategy_name=self.name,
                        confidence=confidence,
                        metadata={
                            "fiftyDayAveragePrice": avg_50,
                            "diff_pct": round(diff_pct, 4),
                            "threshold_pct": self.threshold_pct,
                        },
                    )
                )

        return signals
