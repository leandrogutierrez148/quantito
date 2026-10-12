"""No external dataset: frozen-signal and fixed-capital diagnostic identities."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from quantito.research.strategies.wristwatch.diagnostics import (
    DailyDiagnostics,
    concentration,
    quality_flags,
    scenario_targets,
)
from quantito.research.strategies.wristwatch.execution import account
from tests.research.wristwatch.test_wristwatch import bars


class DiagnosticTests(unittest.TestCase):
    def test_same_windows_preserves_absolute_exposure_and_original(self):
        index = pd.date_range("2015-01-01", periods=8, tz="UTC")
        target = pd.Series([0, 0.15, -0.15, 0, -0.15, 0.15, 0, 0], index=index)
        original = target.copy()
        scenarios = scenario_targets(target)
        pd.testing.assert_series_equal(scenarios["long_same_windows"], target.abs())
        pd.testing.assert_series_equal(scenarios["long_only"] + scenarios["short_only"], target)
        pd.testing.assert_series_equal(target, original)
        self.assertEqual(scenarios["buy_hold_15pct"].iloc[-1], 0)
        self.assertEqual(scenarios["buy_hold_15pct"].iloc[0], 0.15)

    def test_long_and_short_pnl_and_turnover_reconcile_including_reversal(self):
        frame = bars(8, "D")
        target = pd.Series([0, 0.15, 0.15, -0.15, -0.15, 0, 0, 0], index=frame.index)
        scenarios = scenario_targets(target)
        for cost in (0, 5):
            curves = {name: account(frame.open, weight, cost) for name, weight in scenarios.items()}
            np.testing.assert_allclose(
                curves["long_only"].net_bps + curves["short_only"].net_bps,
                curves["long_short"].net_bps,
                atol=1e-12,
            )
            self.assertAlmostEqual(
                curves["long_only"].turnover.sum() + curves["short_only"].turnover.sum(),
                curves["long_short"].turnover.sum(),
            )

    def test_quality_annotations_include_future_interval_but_do_not_modify_prices(self):
        frame = bars(10, "D")
        frame.loc[frame.index[5] :, ["open", "close", "high", "low"]] *= 2
        frame.loc[frame.index[3], "volume"] = 0
        original = frame.copy()
        flags = quality_flags(frame)
        self.assertTrue(flags.close_jump.iloc[5])
        self.assertTrue(flags.forward_open_jump.iloc[4])
        self.assertFalse(flags.forward_open_jump.iloc[5])
        self.assertTrue(flags.zero_volume.iloc[3])
        pd.testing.assert_frame_equal(frame, original)

    def test_flat_prices_and_calendar_gaps(self):
        frame = bars(10, "D")
        frame["close"] = 100.0
        frame.index = frame.index[:5].append(frame.index[5:] + pd.Timedelta(days=12))
        flags = quality_flags(frame)
        self.assertFalse(flags.stale_close.iloc[3])
        self.assertTrue(flags.stale_close.iloc[4])
        self.assertTrue(flags.calendar_gap.iloc[5])
        self.assertTrue(flags.forward_calendar_gap.iloc[4])

    def test_fixed_universe_counts_missing_history_as_cash(self):
        first = bars(4, "D", "2015-01-01")
        second = bars(4, "D", "2015-01-03")
        first.open = [100, 110, 110, 110]
        second.open = [100, 120, 120, 120]
        target_a = pd.Series([0.15, 0, 0, 0], index=first.index)
        target_b = pd.Series([0.15, 0, 0, 0], index=second.index)
        expected = (0.15 * np.log(1.1) + 0.15 * np.log(1.2)) * 100 / 2
        with tempfile.TemporaryDirectory() as directory:
            diagnostic = DailyDiagnostics(directory)
            for symbol, group, frame, target in (
                ("a", "Stock", first, target_a),
                ("b", "ETF", second, target_b),
            ):
                flags = diagnostic.inspect(symbol, group, frame)
                diagnostic.observe(symbol, group, frame.open, target, flags, 0.15)
            with patch.object(diagnostic, "plot"):
                summary = diagnostic.finish()
            all_symbols = summary.loc[
                (summary.group == "ALL")
                & (summary.scenario == "long_short")
                & (summary.cost_bps == 0)
            ].iloc[0]
            self.assertAlmostEqual(all_symbols.net_log_pct, expected)
            self.assertEqual(all_symbols.symbols, 2)
            curve = pd.read_csv(Path(directory) / "diagnostics/equal_weight_curves.csv")
            self.assertAlmostEqual(curve.long_short_0bp.iloc[0], 0.15 * np.log(1.1) * 1e4 / 2)
            quality = json.loads((Path(directory) / "diagnostics/quality_summary.json").read_text())
            self.assertFalse(quality["flags_used_for_signal_or_exclusion"])

    def test_duplicate_symbol_fails_instead_of_double_counting(self):
        frame = bars(4, "D")
        target = pd.Series([0.15, 0, 0, 0], index=frame.index)
        with tempfile.TemporaryDirectory() as directory:
            diagnostic = DailyDiagnostics(directory)
            flags = diagnostic.inspect("a", "Stock", frame)
            diagnostic.observe("a", "Stock", frame.open, target, flags, 0.15)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                diagnostic.observe("a", "Stock", frame.open, target, flags, 0.15)

    def test_concentration_uses_absolute_and_positive_denominators(self):
        values = pd.Series([10.0, -9.0] + [1.0] * 98)
        result = concentration(values)
        self.assertAlmostEqual(result["top_10_absolute_pnl_share"], 27 / 117)
        self.assertAlmostEqual(result["top_1pct_absolute_pnl_share"], 10 / 117)
        self.assertAlmostEqual(result["top_10_positive_pnl_share"], 19 / 108)
        self.assertIsNone(concentration(pd.Series([0.0]))["top_10_absolute_pnl_share"])
