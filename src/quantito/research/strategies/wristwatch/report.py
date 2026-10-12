"""Reproducible attribution, no claim of executable investment returns."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n"
    )


def regimes(prices):
    daily = prices.resample("D").last()
    # Prior calendar day only: trend and volatility cannot change intraday decisions.
    trend = np.log(daily / daily.shift(20)).shift(1)
    vol = np.log(daily / daily.shift()).rolling(20, min_periods=20).std().shift(1)
    regime = pd.Series("unknown", index=daily.index)
    regime.loc[trend.notna() & vol.notna()] = "lateral"
    regime.loc[trend > vol * np.sqrt(20)] = "bull"
    regime.loc[trend < -vol * np.sqrt(20)] = "bear"
    threshold = vol.expanding(min_periods=60).median().shift(1)
    volatility = pd.Series(np.where(vol > threshold, "high", "low"), index=daily.index)
    volatility.loc[threshold.isna() | vol.isna()] = "unknown"
    return regime.reindex(prices.index.floor("D")).set_axis(prices.index), volatility.reindex(
        prices.index.floor("D")
    ).set_axis(prices.index)


def metrics(curve, trades):
    daily = curve.net_bps.resample("D").sum() / 1e4
    annual = 365.25
    sharpe = (
        float(daily.mean() / daily.std(ddof=1) * np.sqrt(annual)) if daily.std(ddof=1) > 0 else None
    )
    duration = (curve.index[-1] - curve.index[0]).total_seconds() / 86400 / annual
    return {
        "observations": len(curve),
        "gross_additive_log_pct": float(curve.gross_bps.sum() / 100),
        "cost_log_pct": float(curve.cost_bps.sum() / 100),
        "net_additive_log_pct": float(curve.net_bps.sum() / 100),
        "max_drawdown_log_pct": float(curve.drawdown_log_pct.min()),
        "illustrative_exponential_return_pct": float(np.expm1(curve.net_bps.sum() / 1e4) * 100),
        "illustrative_exponential_max_drawdown_pct": float(
            np.expm1(curve.drawdown_log_pct.min() / 100) * 100
        ),
        "sharpe_daily_log": sharpe,
        "illustrative_cagr_pct": float(np.expm1(curve.net_bps.sum() / 1e4 / duration) * 100)
        if duration >= 1
        else None,
        "turnover_target_units": float(curve.turnover.sum()),
        "entries": len(trades),
        "exits": len(trades),
        "mean_abs_exposure": float(curve.target.abs().mean()),
        "max_abs_exposure": float(curve.target.abs().max()),
        "hit_rate": float(trades.net_bps.gt(0).mean()) if len(trades) else None,
        "mean_duration_minutes": float(trades.duration_minutes.mean()) if len(trades) else None,
    }


def export_report(directory, curve, trades, prices, context):
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "metrics.json", metrics(curve, trades))
    write_json(out / "context.json", context)
    curve.to_parquet(out / "equity_drawdown.parquet")
    curve[["cumulative_log_pct", "drawdown_log_pct"]].resample("D").last().to_csv(
        out / "equity_drawdown_daily.csv"
    )
    trades.to_csv(out / "trades.csv", index=False)
    regime, volatility = regimes(prices)
    augmented = curve.copy()
    augmented["year"] = curve.index.year
    augmented["regime"] = regime
    augmented["volatility"] = volatility
    augmented["session"] = np.select(
        [curve.index.hour < 8, curve.index.hour < 16],
        ["UTC_00_08", "UTC_08_16"],
        default="UTC_16_24",
    )
    # Allocate entry and exit costs to their economic side, including reversals.
    previous = curve.target.shift(fill_value=0)
    for side, sign in (("long", 1), ("short", -1)):
        side_target = curve.target.clip(lower=0) if sign == 1 else curve.target.clip(upper=0)
        side_turn = side_target.diff().fillna(side_target.iloc[0]).abs()
        costs = side_turn * curve.cost_bps.div(curve.turnover.where(curve.turnover.gt(0))).fillna(0)
        gross = curve.gross_bps.where(curve.target * sign > 0, 0)
        write_json(
            out / f"{side}_metrics.json",
            {
                "gross_log_pct": float(gross.sum() / 100),
                "cost_log_pct": float(costs.sum() / 100),
                "net_log_pct": float((gross - costs).sum() / 100),
            },
        )
    augmented["side"] = np.where(
        curve.target > 0,
        "long",
        np.where(
            curve.target < 0,
            "short",
            np.where(previous > 0, "long_exit", np.where(previous < 0, "short_exit", "flat")),
        ),
    )
    for dimension in ("year", "regime", "session", "volatility"):
        augmented.groupby(dimension)[["gross_bps", "cost_bps", "net_bps", "turnover"]].sum().to_csv(
            out / f"breakdown_{dimension}.csv"
        )
    trades.groupby("side").agg(trades=("net_bps", "count"), net_bps=("net_bps", "sum")).to_csv(
        out / "breakdown_side.csv"
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    daily = curve.resample("D").last()
    axes[0].plot(daily.index, daily.cumulative_log_pct)
    axes[1].plot(daily.index, daily.drawdown_log_pct)
    axes[0].set_ylabel("Additive log PnL (%)")
    axes[1].set_ylabel("Log drawdown (%)")
    axes[0].set_title(context.get("title", "Research only"))
    fig.tight_layout()
    fig.savefig(out / "equity_drawdown.png", dpi=130)
    plt.close(fig)
    (out / "report.md").write_text(
        "# Research-only result\n\n" + context.get("title", "") + "\n\n"
        "PnL is additive target-weighted log return, not a self-financing spot account. "
        "Shorts are hypothetical; borrow, funding, spread and actual fills are excluded. "
        "Previously inspected periods are retrospective.\n\n```json\n"
        + json.dumps(metrics(curve, trades), indent=2)
        + "\n```\n"
    )
