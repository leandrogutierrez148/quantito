"""Independent repricing of the brief's frozen targets, without regenerating signal."""

from pathlib import Path

import numpy as np
import pandas as pd

from quantito.research.strategies.wristwatch.data import sha256
from quantito.research.strategies.wristwatch.execution import account, trades_from_curve
from quantito.research.strategies.wristwatch.report import export_report, metrics, write_json


def replay_reference(root, prices, output):
    root = Path(root)
    jobs = [
        (
            "history_frozen",
            root
            / "btc_multihorizon_is_2017_2024_20261010"
            / "2h_hgb_expanding_2018_2024_curve.parquet",
            0.15,
        )
    ]
    for variant in ("aug_fixed_postfit", "oct_refit_postfit", "jan_refit_train90"):
        jobs.append(
            (
                f"2025_frozen_{variant}",
                root
                / "btc_2h_intermediate_robustness_20261010"
                / f"test_2025_{variant}_30m_curve.parquet",
                1.0,
            )
        )
    rows = []
    provenance = []
    for name, path, scale in jobs:
        frozen = pd.read_parquet(path)
        if (
            frozen.index.has_duplicates
            or str(frozen.index.tz) != "UTC"
            or not frozen.index.is_monotonic_increasing
        ):
            raise ValueError("Invalid frozen reference clock")
        # Original source clock omits the exclusive endpoint. All targets must already be flat.
        if frozen.target.iloc[-1] != 0:
            raise ValueError("Frozen reference has unclosed target")
        end = frozen.index[-1] + pd.Timedelta(minutes=30)
        clock = pd.date_range(frozen.index[0], end, freq="min")
        zero_delay = np.r_[np.repeat(frozen.target.to_numpy(float) * scale, 30), 0.0]
        provenance.append({"file": path.name, "sha256": sha256(path), "scale": scale})
        for delay in (0, 1, 2, 5):
            target = pd.Series(
                np.r_[np.zeros(delay), zero_delay[: len(zero_delay) - delay]]
                if delay
                else zero_delay,
                index=clock,
            )
            actual = prices.reindex(clock)
            for cost in (0.0, 5.0, 10.0):
                try:
                    curve = account(actual, target, cost)
                    trades = trades_from_curve(curve, actual)
                    rows.append(
                        {
                            "period": name,
                            "delay_minutes": delay,
                            "round_trip_cost_bps": cost,
                            "status": "COMPLETE",
                            **metrics(curve, trades),
                        }
                    )
                    if delay == 1 and cost == 5:
                        export_report(
                            Path(output) / name,
                            curve,
                            trades,
                            actual,
                            {
                                "title": name
                                + " / frozen target repricing / official Binance spot",
                                "warning": "This reproduces saved targets, not a model refit; future-validity filters in source can exclude decisions after inspecting missing bars.",
                            },
                        )
                except ValueError as exc:
                    rows.append(
                        {
                            "period": name,
                            "delay_minutes": delay,
                            "round_trip_cost_bps": cost,
                            "status": "BLOCKED_MISSING_REALIZED_DATA",
                            "reason": str(exc),
                        }
                    )
    write_json(Path(output) / "reference_manifest.json", provenance)
    pd.DataFrame(rows).to_csv(Path(output) / "btc_reference_metrics.csv", index=False)
    return rows
