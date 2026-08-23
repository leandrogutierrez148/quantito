import os
import sys
import traceback
import types
import unittest
from unittest import mock

from pipelines import delayed, eod, real_time


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeNotFound(Exception):
    pass


class SecretHTTPError(Exception):
    pass


def install_fake_google_modules(client_factory):
    bigquery_module = types.ModuleType("google.cloud.bigquery")
    bigquery_module.Client = client_factory
    bigquery_module.Dataset = lambda dataset_ref: types.SimpleNamespace(
        dataset_ref=dataset_ref,
        location=None,
    )
    bigquery_module.Table = lambda table_ref, schema=None: types.SimpleNamespace(
        table_ref=table_ref,
        schema=schema,
    )
    bigquery_module.SchemaField = lambda *args, **kwargs: (args, kwargs)

    cloud_module = types.ModuleType("google.cloud")
    cloud_module.bigquery = bigquery_module

    exceptions_module = types.ModuleType("google.api_core.exceptions")
    exceptions_module.NotFound = FakeNotFound

    api_core_module = types.ModuleType("google.api_core")
    api_core_module.exceptions = exceptions_module

    google_module = types.ModuleType("google")
    google_module.cloud = cloud_module
    google_module.api_core = api_core_module

    return {
        "google": google_module,
        "google.cloud": cloud_module,
        "google.cloud.bigquery": bigquery_module,
        "google.api_core": api_core_module,
        "google.api_core.exceptions": exceptions_module,
    }


class PipelineFailureTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["EODHD_API_TOKEN"] = "placeholder"
        os.environ["SYMBOLS"] = "AAPL.US,GOOGL.US"
        os.environ.pop("BIGQUERY_DATASET", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_real_time_storage_failure_is_not_hidden(self):
        with (
            mock.patch.object(
                real_time.requests,
                "get",
                return_value=FakeResponse([{"code": "AAPL.US", "close": 123.4}]),
            ),
            mock.patch.object(
                real_time,
                "store_data",
                side_effect=RuntimeError("bigquery failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "bigquery failed"),
        ):
            real_time.run()

    def test_http_errors_are_sanitized_without_context(self):
        cases = [
            (
                real_time,
                "Error fetching real-time quotes.",
            ),
            (
                delayed,
                "Error fetching US delayed quotes.",
            ),
            (
                eod,
                "Error fetching EOD historical data for symbol AAPL.US.",
            ),
        ]

        for module, expected_message in cases:
            with self.subTest(module=module.__name__):
                with (
                    mock.patch.object(
                        module.requests,
                        "get",
                        side_effect=SecretHTTPError("api_token=SHOULD_NOT_APPEAR"),
                    ),
                    self.assertRaises(RuntimeError) as ctx,
                ):
                    module.run()

                exc = ctx.exception
                self.assertEqual(str(exc), expected_message)
                self.assertTrue(exc.__suppress_context__)
                formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                self.assertNotIn("SHOULD_NOT_APPEAR", formatted)

    def test_real_time_pipeline_success_without_bigquery(self):
        with mock.patch.object(
            real_time.requests,
            "get",
            return_value=FakeResponse([{"code": "AAPL.US", "close": 123.4}]),
        ):
            real_time.run()

    def test_delayed_pipeline_success_without_bigquery(self):
        payload = {
            "data": {
                "AAPL.US": {
                    "symbol": "AAPL.US",
                    "exchange": "XNAS",
                    "lastTradePrice": 123.4,
                    "timestamp": 1,
                }
            }
        }
        with mock.patch.object(delayed.requests, "get", return_value=FakeResponse(payload)):
            delayed.run()

    def test_eod_pipeline_success_without_bigquery(self):
        shared_entry = {
            "date": "2026-08-11",
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "adjusted_close": 1.4,
            "volume": 100,
        }
        responses = [
            FakeResponse([shared_entry]),
            FakeResponse([shared_entry]),
        ]

        with mock.patch.object(eod.requests, "get", side_effect=responses):
            eod.run()
        self.assertNotIn("symbol", shared_entry)

    def test_eod_reused_provider_object_produces_one_row_per_symbol(self):
        shared_entry = {
            "date": "2026-08-11",
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "adjusted_close": 1.4,
            "volume": 100,
        }
        stored_rows = []

        with (
            mock.patch.object(
                eod.requests,
                "get",
                side_effect=[FakeResponse([shared_entry]), FakeResponse([shared_entry])],
            ),
            mock.patch.object(
                eod,
                "store_data",
                side_effect=lambda rows: stored_rows.extend(rows),
            ),
        ):
            eod.run()

        self.assertEqual(len(stored_rows), 2)
        self.assertEqual(
            [row["symbol"] for row in stored_rows],
            ["AAPL.US", "GOOGL.US"],
        )

    def test_real_time_insert_rows_errors_propagate_when_bigquery_is_configured(self):
        os.environ["BIGQUERY_DATASET"] = "quantito"

        class FakeClient:
            def dataset(self, dataset_name):
                return types.SimpleNamespace(
                    dataset_name=dataset_name,
                    table=lambda table_id: f"{dataset_name}.{table_id}",
                )

            def get_dataset(self, dataset_ref):
                return dataset_ref

            def get_table(self, table_ref):
                return table_ref

            def insert_rows_json(self, table_ref, rows):
                return [{"message": "insert failed"}]

        fake_modules = install_fake_google_modules(FakeClient)
        with (
            mock.patch.dict(sys.modules, fake_modules, clear=False),
            self.assertRaisesRegex(RuntimeError, "Errors inserting real-time quotes"),
        ):
            real_time.store_data([{"code": "AAPL.US", "close": 123.4}])

    def test_delayed_bigquery_client_creation_failure_propagates(self):
        os.environ["BIGQUERY_DATASET"] = "quantito"

        def failing_client():
            raise RuntimeError("client init failed")

        fake_modules = install_fake_google_modules(failing_client)
        with (
            mock.patch.dict(sys.modules, fake_modules, clear=False),
            self.assertRaisesRegex(RuntimeError, "client init failed"),
        ):
            delayed.store_data([{"symbol": "AAPL.US", "exchange": "XNAS", "lastTradePrice": 123.4}])

    def test_delayed_bigquery_import_error_propagates_when_configured(self):
        os.environ["BIGQUERY_DATASET"] = "quantito"

        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"google.cloud", "google.api_core.exceptions"}:
                raise ImportError("bigquery missing")
            return real_import(name, globals, locals, fromlist, level)

        with (
            mock.patch("builtins.__import__", side_effect=fake_import),
            self.assertRaisesRegex(ImportError, "bigquery missing"),
        ):
            delayed.store_data([{"symbol": "AAPL.US", "exchange": "XNAS", "lastTradePrice": 123.4}])

    def test_real_time_dataset_creation_failure_propagates(self):
        os.environ["BIGQUERY_DATASET"] = "quantito"

        class FakeClient:
            def dataset(self, dataset_name):
                return types.SimpleNamespace(
                    dataset_name=dataset_name,
                    table=lambda table_id: f"{dataset_name}.{table_id}",
                )

            def get_dataset(self, dataset_ref):
                raise FakeNotFound()

            def create_dataset(self, dataset):
                raise RuntimeError("dataset creation failed")

        fake_modules = install_fake_google_modules(FakeClient)
        with (
            mock.patch.dict(sys.modules, fake_modules, clear=False),
            self.assertRaisesRegex(RuntimeError, "dataset creation failed"),
        ):
            real_time.store_data([{"code": "AAPL.US", "close": 123.4}])

    def test_delayed_table_creation_failure_propagates(self):
        os.environ["BIGQUERY_DATASET"] = "quantito"

        class FakeClient:
            def dataset(self, dataset_name):
                return types.SimpleNamespace(
                    dataset_name=dataset_name,
                    table=lambda table_id: f"{dataset_name}.{table_id}",
                )

            def get_dataset(self, dataset_ref):
                return dataset_ref

            def get_table(self, table_ref):
                raise FakeNotFound()

            def create_table(self, table):
                raise RuntimeError("table creation failed")

        fake_modules = install_fake_google_modules(FakeClient)
        with (
            mock.patch.dict(sys.modules, fake_modules, clear=False),
            self.assertRaisesRegex(RuntimeError, "table creation failed"),
        ):
            delayed.store_data([{"symbol": "AAPL.US", "exchange": "XNAS", "lastTradePrice": 123.4}])

    def test_eod_chunk_insert_exception_propagates(self):
        os.environ["BIGQUERY_DATASET"] = "quantito"

        class FakeClient:
            def dataset(self, dataset_name):
                return types.SimpleNamespace(
                    dataset_name=dataset_name,
                    table=lambda table_id: f"{dataset_name}.{table_id}",
                )

            def get_dataset(self, dataset_ref):
                return dataset_ref

            def get_table(self, table_ref):
                return table_ref

            def insert_rows_json(self, table_ref, rows):
                raise RuntimeError("chunk insert exploded")

        fake_modules = install_fake_google_modules(FakeClient)
        with (
            mock.patch.dict(sys.modules, fake_modules, clear=False),
            self.assertRaisesRegex(RuntimeError, "chunk insert exploded"),
        ):
            eod.store_data(
                [
                    {
                        "symbol": "AAPL.US",
                        "date": "2026-08-11",
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "adjusted_close": 1.4,
                        "volume": 100,
                    }
                ]
            )
