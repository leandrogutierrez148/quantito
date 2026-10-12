"""Synthetic daily label timing and real cache lifecycle checks."""

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from quantito.research.strategies.wristwatch.config import Config
from quantito.research.strategies.wristwatch.daily import (
    annual_training_rows,
    daily_labels,
    daily_target,
    run_daily,
)
from quantito.research.strategies.wristwatch.execution import account
from quantito.research.strategies.wristwatch.signal import FEATURES
from tests.research.wristwatch.test_wristwatch import bars


class DailyLabelTests(unittest.TestCase):
    def test_exact_decision_entry_exit_and_outcome_in_both_modes(self):
        frame = bars(12, "B", "2014-01-01")
        config = Config()
        decision = 2
        scores = pd.DataFrame({"target": [0.15]}, index=frame.index[decision : decision + 1])
        operated = daily_target(frame.index, scores, config)
        self.assertEqual(operated.iloc[decision], 0)
        self.assertEqual(operated.iloc[decision + 1 : decision + 5].tolist(), [0.15] * 4)
        self.assertEqual(operated.iloc[decision + 5], 0)
        aligned = daily_labels(frame, config, "execution_aligned")
        realized = account(frame.open, operated, round_trip_cost_bps=0)
        self.assertAlmostEqual(realized.gross_bps.sum(), 0.15 * aligned.outcome_bps.iloc[decision])
        for mode, entry, exit_index in (
            ("execution_aligned", decision + 1, decision + 5),
            ("source_label_emulation", decision, decision + 4),
        ):
            with self.subTest(mode=mode):
                labels = daily_labels(frame, config, mode)
                row = labels.loc[frame.index[decision]]
                self.assertEqual(labels.index[decision], frame.index[decision])
                self.assertEqual(row.label_entry, frame.index[entry])
                self.assertEqual(row.label_exit, frame.index[exit_index])
                self.assertAlmostEqual(
                    row.outcome_bps,
                    np.log(frame.open.iloc[exit_index] / frame.open.iloc[entry]) * 1e4,
                )

    def test_cutoff_excludes_the_exact_label_exit_for_each_mode(self):
        frame = bars(12, "D", "2012-12-26")
        cutoff = pd.Timestamp("2013-01-01", tz="UTC")
        for mode, accepted in (("execution_aligned", [0]), ("source_label_emulation", [0, 1])):
            labels = daily_labels(frame, Config(), mode)
            features = pd.DataFrame(1.0, index=frame.index, columns=FEATURES).join(labels)
            features["aligned"] = True
            train = annual_training_rows(features, cutoff)
            with self.subTest(mode=mode):
                self.assertEqual(train.index.tolist(), frame.index[accepted].tolist())
                boundary = features.loc[features.label_exit == cutoff]
                self.assertEqual(len(boundary), 1)
                self.assertNotIn(boundary.index[0], train.index)

    def test_custom_delay_and_hold_change_label_and_execution_together(self):
        frame = bars(15, "B", "2014-01-01")
        config = Config(daily_delay_bars=2, hold_bars=3)
        labels = daily_labels(frame, config)
        self.assertEqual(labels.label_entry.iloc[0], frame.index[2])
        self.assertEqual(labels.label_exit.iloc[0], frame.index[5])
        target = daily_target(
            frame.index, pd.DataFrame({"target": [0.15]}, index=frame.index[:1]), config
        )
        self.assertEqual(target.iloc[:6].tolist(), [0, 0, 0.15, 0.15, 0.15, 0])
        self.assertTrue(labels.outcome_bps.iloc[-5:].isna().all())

    def test_unknown_mode_fails(self):
        with self.assertRaises(ValueError):
            daily_labels(bars(), Config(), "invented")


class DailyCacheTests(unittest.TestCase):
    def run_with_cache_capture(self, fail=False):
        factory = tempfile.TemporaryDirectory
        paths = []
        with factory() as parent:
            root = Path(parent)
            dataset = root / "synthetic.zip"
            frame = bars(1600, "B", "2009-01-01")
            daily = frame[["open", "high", "low", "close", "volume"]].copy()
            daily.columns = ["Open", "High", "Low", "Close", "Volume"]
            daily.insert(0, "Date", frame.index.strftime("%Y-%m-%d"))
            daily["OpenInt"] = 0
            with zipfile.ZipFile(dataset, "w") as archive:
                archive.writestr("Stocks/synthetic.us.txt", daily.to_csv(index=False))

            def capture(**kwargs):
                directory = factory(dir=root, **kwargs)
                paths.append(Path(directory.name))
                return directory

            def failure(*args):
                self.assertTrue(list(paths[0].glob("*.parquet")))
                raise RuntimeError("synthetic fit failure after cache write")

            with patch(
                "quantito.research.strategies.wristwatch.daily.tempfile.TemporaryDirectory", capture
            ):
                if fail:
                    with (
                        patch(
                            "quantito.research.strategies.wristwatch.daily.make_model",
                            side_effect=failure,
                        ),
                        self.assertRaisesRegex(RuntimeError, "synthetic fit failure"),
                    ):
                        run_daily(dataset, root / "output", Config(max_iter=3), years=[2013])
                else:
                    summary = run_daily(dataset, root / "output", Config(max_iter=3), years=[2013])
                    self.assertEqual(summary["evaluated_symbols"], 1)
                    self.assertEqual(summary["label_mode"], "execution_aligned")
            self.assertEqual(len(paths), 1)
            self.assertFalse(paths[0].exists())

    def test_cache_removed_after_success(self):
        self.run_with_cache_capture()

    def test_cache_removed_after_processing_exception(self):
        self.run_with_cache_capture(fail=True)
