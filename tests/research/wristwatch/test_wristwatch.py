"""Synthetic-only invariants for temporal safety, accounting and data quality."""

import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from quantito.research.strategies.wristwatch.config import Config
from quantito.research.strategies.wristwatch.daily import daily_target
from quantito.research.strategies.wristwatch.data import (
    audit_zip,
    canonical_members,
    load_panels,
    read_binance_zip,
    resample_minutes,
    validate_bars,
)
from quantito.research.strategies.wristwatch.execution import (
    account,
    targets_from_scores,
    trades_from_curve,
)
from quantito.research.strategies.wristwatch.report import metrics, regimes, write_json
from quantito.research.strategies.wristwatch.signal import (
    FEATURES,
    build_features,
    fit_scores,
    make_model,
)


def bars(n=1000, freq="30min", start="2017-09-01"):
    clock = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    close = 100 * np.exp(np.sin(np.arange(n) / 15) * 0.01 + np.arange(n) * 0.00001)
    frame = pd.DataFrame(
        {
            "open": close,
            "close": close,
            "high": close * 1.002,
            "low": close * 0.998,
            "volume": 100.0,
            "quote_volume": close * 100,
        },
        index=clock,
    )
    frame["prior_close"] = frame.close.shift(1)
    frame["sigma60"] = 0.001
    frame["z60"] = np.sin(np.arange(n) / 21)
    frame["bar_complete"] = True
    return frame


class ConfigurationTests(unittest.TestCase):
    def test_hash_is_stable_and_sensitive(self):
        self.assertEqual(Config().digest, Config().digest)
        self.assertNotEqual(Config().digest, Config(target=0.2).digest)

    def test_nonfinite_values_fail(self):
        for field in ("target", "gate_quantile", "round_trip_cost_bps"):
            for value in (np.nan, np.inf, -np.inf):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    Config(**{field: value})

    def test_invalid_delays_and_counts_fail(self):
        for field in ("hold_bars", "execution_delay_minutes", "max_iter", "daily_delay_bars"):
            for value in (0, -1, 1.5, True):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    Config(**{field: value})


class DataTests(unittest.TestCase):
    def test_rejects_naive_timezone(self):
        frame = bars()
        frame.index = frame.index.tz_localize(None)
        with self.assertRaises(ValueError):
            validate_bars(frame)

    def test_rejects_duplicates(self):
        frame = bars()
        with self.assertRaises(ValueError):
            validate_bars(pd.concat([frame, frame.iloc[:1]]))

    def test_rejects_disordered_clock(self):
        with self.assertRaises(ValueError):
            validate_bars(bars().iloc[::-1])

    def test_invalid_candle_fails(self):
        frame = bars()
        frame.iloc[0, frame.columns.get_loc("high")] = 1
        with self.assertRaises(ValueError):
            validate_bars(frame)

    def test_resampling_exact_30_minutes(self):
        frame = bars(120, "min")
        result = resample_minutes(frame)
        self.assertEqual(len(result), 4)
        self.assertEqual(result.minute_count.tolist(), [30] * 4)
        self.assertEqual(result.open.iloc[0], frame.open.iloc[0])
        self.assertEqual(result.close.iloc[0], frame.close.iloc[29])

    def test_gap_not_interpolated(self):
        frame = bars(120, "min").drop(bars(120, "min").index[35])
        result = resample_minutes(frame)
        self.assertFalse(result.bar_complete.iloc[1])
        self.assertTrue(np.isnan(result.open.iloc[1]))
        self.assertTrue(np.isnan(result.z60.iloc[-1]))

    def test_daily_is_not_minute(self):
        # The intraday resampler must not turn a daily file into usable minute bars.
        result = resample_minutes(bars(3, "D"))
        self.assertFalse(result.bar_complete.any())
        self.assertTrue(result.open.isna().all())

    def test_binance_millisecond_and_microsecond_formats(self):
        for scale in (1000, 1_000_000):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "sample.zip"
                timestamp = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp() * scale)
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(
                        "sample.csv", f"{timestamp},100,101,99,100,10,0,1000,2,0,0,0\n"
                    )
                self.assertEqual(
                    read_binance_zip(path).index[0], pd.Timestamp("2025-01-01", tz="UTC")
                )

    def test_mirror_audit_and_incompatible_daily(self):
        content = "Date,Open,High,Low,Close,Volume,OpenInt\n2017-01-03,100,101,99,100,10,0\n2017-01-04,100,101,99,100,10,0\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Data/Stocks/a.us.txt", content)
                archive.writestr("Stocks/a.us.txt", content)
            audit = audit_zip(path)
            self.assertEqual(audit["unique_symbols"], 1)
            self.assertEqual(audit["mirrored_files"], 1)
            self.assertEqual(audit["frequency"], "daily")

    def test_off_minute_is_rejected_or_quarantined_never_rounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            minute = int(pd.Timestamp("2018-01-01", tz="UTC").timestamp() * 1000)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "sample.csv",
                    f"{minute},100,101,99,100,10,0,1000,2,0,0,0\n"
                    f"{minute + 60001},200,201,199,200,10,0,2000,2,0,0,0\n"
                    f"{minute + 120000},100,101,99,100,10,0,1000,2,0,0,0\n",
                )
            with self.assertRaisesRegex(ValueError, "Off-minute"):
                read_binance_zip(path)
            result = read_binance_zip(path, quarantine_off_minute=True)
            self.assertEqual(len(result), 2)
            self.assertEqual(result.attrs["quarantined_off_minute_rows"], 1)
            self.assertEqual(result.index.to_series().diff().iloc[-1], pd.Timedelta(minutes=2))

    def test_parquet_microsecond_index_is_same_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            frame = bars(8)
            frame.index = frame.index.as_unit("us")
            frame.to_parquet(Path(directory) / "btc_decisions_2017-09.parquet")
            loaded, manifest = load_panels([directory])
            self.assertEqual(len(loaded), 8)
            self.assertEqual(len(manifest), 1)
            self.assertEqual(loaded.index.dtype, pd.DatetimeIndex(frame.index).as_unit("ns").dtype)

    def test_conflicting_mirror_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Data/a.txt", "one")
                archive.writestr("a.txt", "two")
            with zipfile.ZipFile(path) as archive, self.assertRaises(ValueError):
                canonical_members(archive)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.clock = pd.date_range("2025-01-01", periods=8, freq="min", tz="UTC")
        self.scores = pd.DataFrame({"target": [0.15]}, index=self.clock[:1])

    def test_exact_delay_and_hold(self):
        target = targets_from_scores(self.clock, self.scores, delay_minutes=1, hold_minutes=2)
        self.assertEqual(target.tolist(), [0, 0.15, 0.15, 0, 0, 0, 0, 0])

    def test_overlapping_positions_fail(self):
        scores = pd.DataFrame({"target": [0.15, -0.15]}, index=self.clock[:2])
        with self.assertRaises(ValueError):
            targets_from_scores(self.clock, scores, hold_minutes=3)

    def test_cost_round_trip_not_double_counted(self):
        target = targets_from_scores(self.clock, self.scores, hold_minutes=2)
        prices = pd.Series(100.0, index=self.clock)
        curve = account(prices, target, 5)
        self.assertAlmostEqual(curve.cost_bps.sum(), 0.15 * 5)
        self.assertAlmostEqual(curve.gross_bps.sum(), 0)
        trades = trades_from_curve(curve, prices)
        self.assertAlmostEqual(trades.cost_bps.sum(), curve.cost_bps.sum())

    def test_long_and_short_mark_to_market(self):
        target = targets_from_scores(self.clock, self.scores, hold_minutes=2)
        prices = pd.Series([100, 100, 105, 110, 110, 110, 110, 110], index=self.clock)
        long = account(prices, target, 0)
        short = account(prices, -target, 0)
        self.assertAlmostEqual(long.gross_bps.sum(), 0.15 * np.log(1.1) * 1e4)
        self.assertAlmostEqual(short.gross_bps.sum(), -long.gross_bps.sum())

    def test_missing_realized_price_fails(self):
        target = targets_from_scores(self.clock, self.scores, hold_minutes=2)
        prices = pd.Series(100.0, index=self.clock)
        prices.iloc[2] = np.nan
        with self.assertRaises(ValueError):
            account(prices, target)

    def test_missing_price_in_cash_is_permitted(self):
        prices = pd.Series(np.nan, index=self.clock)
        curve = account(prices, pd.Series(0.0, index=self.clock))
        self.assertEqual(curve.net_bps.sum(), 0)

    def test_missing_exit_price_fails(self):
        target = targets_from_scores(self.clock, self.scores, hold_minutes=2)
        prices = pd.Series(100.0, index=self.clock)
        prices.iloc[3] = np.nan
        with self.assertRaises(ValueError):
            account(prices, target)

    def test_unclosed_position_fails(self):
        with self.assertRaises(ValueError):
            account(pd.Series(100.0, index=self.clock), pd.Series(0.15, index=self.clock))

    def test_reversal_costs_reconcile_trades(self):
        target = pd.Series([0, 0.15, 0.15, -0.15, -0.15, 0, 0, 0], index=self.clock)
        prices = pd.Series(100.0, index=self.clock)
        curve = account(prices, target)
        trades = trades_from_curve(curve, prices)
        self.assertEqual(trades.side.tolist(), ["long", "short"])
        self.assertAlmostEqual(trades.net_bps.sum(), curve.net_bps.sum())

    def test_year_split_never_crossed(self):
        clock = pd.date_range("2024-12-31 23:58", periods=8, freq="min", tz="UTC")
        scores = pd.DataFrame({"target": [0.15]}, index=clock[:1])
        target = targets_from_scores(
            clock, scores, hold_minutes=2, period_end=pd.Timestamp("2025-01-01", tz="UTC")
        )
        self.assertEqual(target.sum(), 0)

    def test_daily_adaptation_next_bar(self):
        clock = pd.bdate_range("2015-01-01", periods=10, tz="UTC")
        scores = pd.DataFrame({"target": [0.15]}, index=clock[:1])
        target = daily_target(clock, scores, Config())
        self.assertEqual(target.tolist(), [0, 0.15, 0.15, 0.15, 0.15, 0, 0, 0, 0, 0])


class CausalityTests(unittest.TestCase):
    def test_feature_metamorphic_future_mutation(self):
        panel = bars()
        reference = build_features(panel)
        changed = panel.copy()
        for column in (
            "open",
            "close",
            "high",
            "low",
            "volume",
            "quote_volume",
            "prior_close",
            "sigma60",
            "z60",
        ):
            changed.loc[changed.index > panel.index[700], column] *= 37
        pd.testing.assert_series_equal(reference.iloc[700], build_features(changed).iloc[700])

    def test_refit_and_decision_metamorphic_future_mutation(self):
        panel = bars(9000, "2h")
        # Make this a continuous 30m panel as required by the actual signal.
        panel = bars(9000 * 4, "30min")
        first, fits = fit_scores(panel, Config(max_iter=3), years=[2018])
        decision = first.index[80]
        changed = panel.copy()
        changed.loc[changed.index > decision, ["open", "close", "high", "low", "quote_volume"]] *= (
            13
        )
        second, second_fits = fit_scores(changed, Config(max_iter=3), years=[2018])
        self.assertEqual(first.loc[decision, "target"], second.loc[decision, "target"])
        self.assertEqual(
            first.loc[decision, "prediction_bps"], second.loc[decision, "prediction_bps"]
        )
        self.assertEqual(fits, second_fits)
        self.assertLess(
            pd.Timestamp(fits[0]["last_label_exit"]), pd.Timestamp(fits[0]["fit_cutoff"])
        )

    def test_fixed_seed_model(self):
        rng = np.random.default_rng(4)
        x = pd.DataFrame(rng.normal(size=(500, 14)), columns=FEATURES)
        y = x.iloc[:, 0] * 3
        a = make_model(500, Config(max_iter=3))
        b = make_model(500, Config(max_iter=3))
        a.fit(x, y)
        b.fit(x, y)
        np.testing.assert_array_equal(a.predict(x), b.predict(x))

    def test_regimes_use_previous_day(self):
        prices = bars(100, "D").open
        regime, _ = regimes(prices)
        mutated = prices.copy()
        mutated.iloc[70:] *= 100
        second, _ = regimes(mutated)
        self.assertEqual(regime.iloc[70], second.iloc[70])


class ReportTests(unittest.TestCase):
    def test_drawdown_includes_initial_zero_peak(self):
        clock = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
        prices = pd.Series([100, 90, 90], index=clock)
        target = pd.Series([1.0, 0, 0], index=clock)
        curve = account(prices, target, 0)
        expected = np.log(0.9) * 100
        self.assertAlmostEqual(curve.drawdown_log_pct.min(), expected)
        self.assertAlmostEqual(
            metrics(curve, trades_from_curve(curve, prices))["max_drawdown_log_pct"], expected
        )

    def test_json_rejects_nan(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            write_json(Path(directory) / "metrics.json", {"return": np.nan})

    def test_zero_strategy_metrics(self):
        frame = bars(10, "D")
        curve = account(frame.open, pd.Series(0.0, index=frame.index))
        report = metrics(curve, trades_from_curve(curve, frame.open))
        self.assertEqual(report["entries"], 0)
        self.assertEqual(report["net_additive_log_pct"], 0)
        self.assertIsNone(report["hit_rate"])
