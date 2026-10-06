import unittest

from fastapi.testclient import TestClient

from engine.server import app
from engine.strategies.base import BaseStrategy
from engine.strategies.registry import StrategyRegistry


class TestFastAPIServer(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check_endpoints(self):
        for path in ("/health", "/api/v1/health"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data.get("status"), "ok")
            self.assertIn("timestamp", data)

    def test_list_strategies_endpoint(self):
        response = self.client.get("/api/v1/strategies")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        strategies = data.get("strategies", [])
        self.assertIsInstance(strategies, list)
        self.assertIn("fifty_day_avg", strategies)
        self.assertIn("price_momentum", strategies)

    def test_evaluate_fifty_day_avg_success(self):
        market_data = [
            {
                "symbol": "AAPL.US",
                "close": 160.0,
                "fiftyDayAveragePrice": 150.0,
            }
        ]
        payload = {
            "symbol": "AAPL.US",
            "params": {"threshold_pct": 1.0},
            "market_data": market_data,
        }

        response = self.client.post("/api/v1/strategies/fifty_day_avg/evaluate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("strategy"), "fifty_day_avg")
        self.assertIn("signals", data)
        self.assertIsInstance(data["signals"], list)
        self.assertEqual(len(data["signals"]), 1)
        self.assertEqual(data["signals"][0]["symbol"], "AAPL.US")
        self.assertEqual(data["signals"][0]["signal_type"], "BUY")

    def test_evaluate_price_momentum_success(self):
        market_data = [
            {
                "symbol": "MSFT.US",
                "close": 400.0,
                "change_p": 2.5,
            }
        ]
        payload = {
            "symbol": "MSFT.US",
            "params": {"min_change_pct": 1.5},
            "market_data": market_data,
        }

        response = self.client.post("/api/v1/strategies/price_momentum/evaluate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("strategy"), "price_momentum")
        self.assertIn("signals", data)
        self.assertEqual(len(data["signals"]), 1)
        self.assertEqual(data["signals"][0]["symbol"], "MSFT.US")
        self.assertEqual(data["signals"][0]["signal_type"], "BUY")

    def test_evaluate_unknown_strategy_returns_404(self):
        response = self.client.post(
            "/api/v1/strategies/non_existent_strategy/evaluate",
            json={"market_data": []},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_evaluate_invalid_params_type_returns_422(self):
        response = self.client.post(
            "/api/v1/strategies/fifty_day_avg/evaluate",
            json={"params": "not-a-dict"},
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_path_returns_404(self):
        response = self.client.get("/api/v1/non_existent_path")
        self.assertEqual(response.status_code, 404)

    def test_strategy_execution_error_handled_gracefully(self):
        class FaultyStrategy(BaseStrategy):
            @property
            def name(self) -> str:
                return "faulty_fastapi_strategy"

            def generate_signals(self, market_data):
                raise RuntimeError("Simulated strategy computation failure")

        StrategyRegistry.register("faulty_fastapi_strategy")(FaultyStrategy)

        response = self.client.post(
            "/api/v1/strategies/faulty_fastapi_strategy/evaluate",
            json={"market_data": [{"close": 100.0}]},
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())
