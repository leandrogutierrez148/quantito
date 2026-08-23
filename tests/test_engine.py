import datetime
import os
import unittest
from unittest.mock import MagicMock, patch

from engine import (
    BaseSignalSink,
    BaseStrategy,
    Signal,
    SignalEngine,
    SignalType,
    StrategyRegistry,
)
from engine.strategies.fifty_day_avg import FiftyDayAverageStrategy
from engine.strategies.price_momentum import PriceMomentumStrategy


class DummyTestStrategy(BaseStrategy):
    def __init__(self, multiplier: int = 1, **kwargs):
        super().__init__(multiplier=multiplier, **kwargs)
        self.multiplier = multiplier

    @property
    def name(self) -> str:
        return "dummy_test"

    def generate_signals(self, market_data):
        return [
            Signal(
                symbol="TEST.US",
                signal_type=SignalType.BUY,
                price=100.0 * self.multiplier,
                strategy_name=self.name,
            )
        ]


class TestSignalEngine(unittest.TestCase):
    def setUp(self):
        # Register a mock strategy for testing
        StrategyRegistry.register("dummy_test")(DummyTestStrategy)

    def test_models_serialization(self):
        now = datetime.datetime.now(datetime.UTC)
        sig = Signal(
            symbol="AAPL.US",
            signal_type=SignalType.BUY,
            price=150.25,
            timestamp=now,
            strategy_name="fifty_day_avg",
            confidence=0.85,
            metadata={"test_key": "test_val"},
        )
        data = sig.to_dict()
        self.assertEqual(data["symbol"], "AAPL.US")
        self.assertEqual(data["signal_type"], "BUY")
        self.assertEqual(data["price"], 150.25)
        self.assertEqual(data["confidence"], 0.85)
        self.assertEqual(data["strategy_name"], "fifty_day_avg")
        self.assertEqual(data["metadata"]["test_key"], "test_val")

    def test_registry_create_and_list(self):
        available = StrategyRegistry.list_strategies()
        self.assertIn("fifty_day_avg", available)
        self.assertIn("price_momentum", available)
        self.assertIn("dummy_test", available)

        # Create with custom params
        strategy = StrategyRegistry.create("dummy_test", multiplier=5)
        self.assertIsInstance(strategy, DummyTestStrategy)
        self.assertEqual(strategy.multiplier, 5)

        # Unknown strategy raises ValueError
        with self.assertRaises(ValueError):
            StrategyRegistry.create("non_existent_strategy_xyz")

    def test_fifty_day_avg_strategy_buy_and_sell(self):
        strategy = FiftyDayAverageStrategy(threshold_pct=1.0, signal_on="both")

        market_data = [
            # 1. Above 50-day average by > 1.0% -> BUY
            {
                "symbol": "AAPL.US",
                "lastTradePrice": 110.0,
                "fiftyDayAveragePrice": 100.0,  # +10%
            },
            # 2. Below 50-day average by > 1.0% -> SELL
            {
                "symbol": "GOOGL.US",
                "lastTradePrice": 90.0,
                "fiftyDayAveragePrice": 100.0,  # -10%
            },
            # 3. Within threshold (0.5% diff) -> NO SIGNAL
            {
                "symbol": "MSFT.US",
                "lastTradePrice": 100.5,
                "fiftyDayAveragePrice": 100.0,  # +0.5%
            },
        ]

        signals = strategy.generate_signals(market_data)
        self.assertEqual(len(signals), 2)

        self.assertEqual(signals[0].symbol, "AAPL.US")
        self.assertEqual(signals[0].signal_type, SignalType.BUY)
        self.assertEqual(signals[0].price, 110.0)

        self.assertEqual(signals[1].symbol, "GOOGL.US")
        self.assertEqual(signals[1].signal_type, SignalType.SELL)
        self.assertEqual(signals[1].price, 90.0)

    def test_price_momentum_strategy(self):
        strategy = PriceMomentumStrategy(min_change_pct=2.0)

        market_data = [
            {"code": "TSLA.US", "close": 200.0, "change_p": 2.5},  # BUY (> 2.0%)
            {"code": "AMZN.US", "close": 120.0, "change_p": -3.1},  # SELL (< -2.0%)
            {"code": "META.US", "close": 300.0, "change_p": 1.1},  # NO SIGNAL (< 2.0%)
        ]

        signals = strategy.generate_signals(market_data)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0].symbol, "TSLA.US")
        self.assertEqual(signals[0].signal_type, SignalType.BUY)
        self.assertEqual(signals[1].symbol, "AMZN.US")
        self.assertEqual(signals[1].signal_type, SignalType.SELL)

    def test_signal_engine_execution_and_hot_swap(self):
        strategy_1 = DummyTestStrategy(multiplier=1)
        mock_sink = MagicMock(spec=BaseSignalSink)

        engine = SignalEngine(strategy=strategy_1, sinks=[mock_sink])
        self.assertEqual(engine.strategy.name, "dummy_test")

        # Process with strategy 1
        signals = engine.process([{"dummy": "data"}])
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].price, 100.0)
        mock_sink.send.assert_called_once_with(signals)

        # Hot-swap strategy to PriceMomentumStrategy
        strategy_2 = PriceMomentumStrategy(min_change_pct=1.0)
        engine.set_strategy(strategy_2)
        self.assertEqual(engine.strategy.name, "price_momentum")

        # Process with strategy 2
        signals_2 = engine.process([{"code": "NVDA.US", "close": 500.0, "change_p": 4.0}])
        self.assertEqual(len(signals_2), 1)
        self.assertEqual(signals_2[0].symbol, "NVDA.US")
        self.assertEqual(signals_2[0].strategy_name, "price_momentum")

    @patch.dict(
        os.environ,
        {
            "STRATEGY_NAME": "fifty_day_avg",
            "STRATEGY_PARAMS": '{"threshold_pct": 3.5, "signal_on": "above"}',
            "ENABLE_BQ_SIGNALS": "false",
        },
    )
    def test_from_environment(self):
        engine = SignalEngine.from_environment()
        self.assertEqual(engine.strategy.name, "fifty_day_avg")
        self.assertIsInstance(engine.strategy, FiftyDayAverageStrategy)
        self.assertEqual(engine.strategy.threshold_pct, 3.5)
        self.assertEqual(engine.strategy.signal_on, "above")


if __name__ == "__main__":
    unittest.main()
