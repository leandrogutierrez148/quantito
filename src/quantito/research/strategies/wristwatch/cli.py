"""Offline research CLI. All sources and output paths are explicit."""

import argparse
import json
import platform
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from quantito.research.strategies.wristwatch.config import Config
from quantito.research.strategies.wristwatch.daily import run_daily
from quantito.research.strategies.wristwatch.data import (
    audit_zip,
    load_panels,
    read_binance_zip,
    resample_minutes,
    sha256,
)
from quantito.research.strategies.wristwatch.download import download_months
from quantito.research.strategies.wristwatch.execution import (
    account,
    targets_from_scores,
    trades_from_curve,
)
from quantito.research.strategies.wristwatch.reference import replay_reference
from quantito.research.strategies.wristwatch.report import export_report, metrics, write_json
from quantito.research.strategies.wristwatch.signal import fit_scores

VARIANTS = ("aug_fixed_postfit", "oct_refit_postfit", "jan_refit_train90")


def run_btc(args, config):
    out = Path(args.output)
    write_json(
        out / "frozen_config.json",
        {
            "config": asdict(config),
            "sha256": config.digest,
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "periods": {
                "history": "2018-01-01/2024-08-03",
                "2025": "2025-01-02/2026-01-01",
                "2026": "2026-01-02/latest complete source",
            },
            "2025_status": "already inspected, retrospective",
            "2026_status": "frozen before this evaluation; local research may have inspected 2026, do not claim pristine holdout",
        },
    )
    panel, source = load_panels(args.panel_dir)
    download_manifest_path = Path(args.binance_dir) / "download_manifest.json"
    if not download_manifest_path.exists():
        raise ValueError("Missing verified Binance download manifest")
    verified = {
        row["file"]: row
        for row in json.loads(download_manifest_path.read_text())
        if row["status"] == "VERIFIED"
    }
    raw_parts = []
    minute_manifest = []
    for path in sorted(Path(args.binance_dir).glob("BTCUSDT-1m-*.zip")):
        if path.name not in verified or sha256(path) != verified[path.name]["sha256"]:
            raise ValueError(f"Unverified or changed archive: {path.name}")
        raw = read_binance_zip(path, quarantine_off_minute=True)
        raw_parts.append(raw)
        minute_manifest.append(
            {
                "file": path.name,
                "sha256": sha256(path),
                "start": str(raw.index[0]),
                "end": str(raw.index[-1]),
                "rows": len(raw),
                "quarantined_off_minute_rows": raw.attrs.get("quarantined_off_minute_rows", 0),
                "exchange": "Binance",
                "market": "spot",
                "symbol": "BTCUSDT",
                "interval": "1m",
            }
        )
    if not raw_parts:
        raise ValueError("No verified Binance minute ZIPs; use download command")
    raw = pd.concat(raw_parts).sort_index()
    if raw.index.has_duplicates:
        raise ValueError("Overlapping minute archives")
    prices = raw.open.reindex(pd.date_range(raw.index[0], raw.index[-1], freq="min"))
    prices.to_frame().to_parquet(out / "btc_minute_prices.parquet")
    # Extend only after cached source end, retaining a long prior feature warmup.
    if raw.index[-1] > panel.index[-1] + pd.Timedelta(days=1):
        extra = resample_minutes(raw.loc[raw.index >= panel.index[-1] - pd.Timedelta(days=10)])
        extra = extra.loc[extra.index > panel.index[-1]]
        panel = pd.concat([panel, extra])
    write_json(
        out / "data_manifest.json",
        {
            "panels": source,
            "minutes": minute_manifest,
            "minute_gaps": int(prices.isna().sum()),
            "unmixed_exchange": "Binance BTCUSDT spot",
            "note": "Signals through 2025 use persisted source panels; prices use independently checksum-verified official Binance archives. 2026 features rebuilt from official OHLCV.",
        },
    )
    if args.reference_dir is not None:
        replay_reference(args.reference_dir, prices, out)
    scores, fits = fit_scores(panel, config, variants=VARIANTS)
    scores.to_parquet(out / "scored_decisions.parquet")
    write_json(out / "fit_records.json", fits)
    summaries = []
    periods = [
        (
            "history",
            pd.Timestamp("2018-01-01", tz="UTC"),
            pd.Timestamp("2024-08-03", tz="UTC"),
            ("jan_refit_train90",),
        ),
        (
            "2025",
            pd.Timestamp("2025-01-02", tz="UTC"),
            pd.Timestamp("2026-01-01", tz="UTC"),
            VARIANTS,
        ),
    ]
    recent_stop = min(panel.index[-1], prices.index[-1]).floor("D")
    if recent_stop > pd.Timestamp("2026-01-03", tz="UTC"):
        periods.append(("2026", pd.Timestamp("2026-01-02", tz="UTC"), recent_stop, VARIANTS))
    for period, start, end, variants in periods:
        for variant in variants:
            chosen = scores.loc[
                (scores.variant == variant) & (scores.index >= start) & (scores.index < end)
            ]
            for delay in (0, 1, 2, 5):
                for cost in (0.0, 5.0, 10.0):
                    minute_clock = pd.date_range(start, end, freq="min")
                    target = targets_from_scores(
                        minute_clock, chosen, delay_minutes=delay, period_end=end
                    )
                    actual = prices.reindex(minute_clock)
                    try:
                        curve = account(actual, target, cost)
                        trades = trades_from_curve(curve, actual)
                        row = {
                            "period": period,
                            "variant": variant,
                            "delay_minutes": delay,
                            "round_trip_cost_bps": cost,
                            "status": "COMPLETE",
                            **metrics(curve, trades),
                        }
                        if (
                            delay == config.execution_delay_minutes
                            and cost == config.round_trip_cost_bps
                        ):
                            export_report(
                                out / f"{period}_{variant}",
                                curve,
                                trades,
                                actual,
                                {
                                    "title": f"BTC {period} / {variant} / exact minute / {delay}m / {cost}bp",
                                    "config_hash": config.digest,
                                },
                            )
                    except ValueError as exc:
                        row = {
                            "period": period,
                            "variant": variant,
                            "delay_minutes": delay,
                            "round_trip_cost_bps": cost,
                            "status": "BLOCKED_MISSING_REALIZED_DATA",
                            "reason": str(exc),
                        }
                    summaries.append(row)
            # Price-mark comparison on the same frozen signals; optimistic same-time execution.
            clock = pd.date_range(start, end, freq="30min")
            target = targets_from_scores(clock, chosen, delay_minutes=0, period_end=end)
            actual = prices.reindex(clock)
            try:
                curve = account(actual, target, config.round_trip_cost_bps)
                summaries.append(
                    {
                        "period": period,
                        "variant": variant,
                        "mark": "30min_optimistic",
                        "delay_minutes": 0,
                        "round_trip_cost_bps": config.round_trip_cost_bps,
                        "status": "COMPLETE",
                        **metrics(curve, trades_from_curve(curve, actual)),
                    }
                )
            except ValueError as exc:
                summaries.append(
                    {
                        "period": period,
                        "variant": variant,
                        "mark": "30min_optimistic",
                        "status": "BLOCKED",
                        "reason": str(exc),
                    }
                )
            print(f"priced {period} {variant}", flush=True)
    summary = pd.DataFrame(summaries)
    summary.to_csv(out / "btc_period_metrics.csv", index=False)
    fixed = summary.loc[
        summary.status.eq("COMPLETE")
        & summary.delay_minutes.eq(config.execution_delay_minutes)
        & summary.round_trip_cost_bps.eq(config.round_trip_cost_bps)
    ]
    sensitivity = []
    for _, row in fixed.iterrows():
        for target in (0.05, 0.10, 0.15, 0.20):
            sensitivity.append(
                {
                    "period": row.period,
                    "variant": row.variant,
                    "target": target,
                    "net_additive_log_pct": row.net_additive_log_pct * target / config.target,
                    "max_drawdown_log_pct": row.max_drawdown_log_pct * target / config.target,
                    "method": "analytic linear rescale of fixed decisions; retrospective diagnostic, not parameter selection",
                }
            )
    pd.DataFrame(sensitivity).to_csv(out / "btc_target_sensitivity.csv", index=False)
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Research-only Wristwatch BTC and separate daily adaptation"
    )
    parser.add_argument(
        "--experiment", choices=["audit", "daily-cross-asset", "btc", "download"], required=True
    )
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/wristwatch"))
    parser.add_argument("--binance-dir", type=Path)
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--panel-dir", type=Path, action="append", default=[])
    parser.add_argument("--first-month", default="2017-09")
    parser.add_argument("--last-month", default="2026-09")
    parser.add_argument("--target", type=float, default=0.15)
    parser.add_argument("--cost-bps", type=float, default=5)
    parser.add_argument("--delay-minutes", type=int, default=1)
    args = parser.parse_args(argv)
    config = Config(
        target=args.target,
        round_trip_cost_bps=args.cost_bps,
        execution_delay_minutes=args.delay_minutes,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    if args.experiment == "download":
        if args.binance_dir is None:
            parser.error("--binance-dir required and must be outside repo")
        download_months(args.binance_dir, args.first_month, args.last_month)
    elif args.experiment in ("audit", "daily-cross-asset"):
        if args.dataset is None:
            parser.error("--dataset required")
        audit = audit_zip(args.dataset)
        write_json(args.output / "leandro_dataset_audit.json", audit)
        if args.experiment == "daily-cross-asset":
            if audit["frequency"] != "daily":
                raise ValueError("Daily adaptation cannot silently accept mixed frequencies")
            run_daily(args.dataset, args.output, config)
    else:
        if args.binance_dir is None or not args.panel_dir:
            parser.error("--binance-dir and --panel-dir required")
        run_btc(args, config)
