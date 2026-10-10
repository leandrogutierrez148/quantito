"""Target accounting; strict prices, cost per side and no overlapping sleeves."""

import numpy as np
import pandas as pd


def targets_from_scores(clock, scores, *, hold_minutes=120, delay_minutes=1, period_end=None):
    if delay_minutes < 0 or hold_minutes < 1:
        raise ValueError("Invalid execution timing")
    target = pd.Series(0.0, index=clock)
    end = period_end or clock[-1]
    for timestamp, row in scores.loc[scores.target.ne(0)].sort_index().iterrows():
        # Exit must fit in the known evaluation split, regardless of future prices.
        entry = timestamp + pd.Timedelta(minutes=delay_minutes)
        exit_time = entry + pd.Timedelta(minutes=hold_minutes)
        annual_end = pd.Timestamp(f"{timestamp.year + 1}-01-01", tz="UTC")
        if exit_time >= min(end, annual_end):
            continue
        first = clock.searchsorted(entry)
        stop = clock.searchsorted(exit_time)
        if (
            first >= len(clock)
            or clock[first] != entry
            or stop >= len(clock)
            or clock[stop] != exit_time
        ):
            raise ValueError("Missing exact execution clock")
        if target.iloc[first:stop].ne(0).any():
            raise ValueError("Overlapping positions")
        target.iloc[first:stop] = row.target
    return target


def account(prices, target, round_trip_cost_bps=5.0):
    if not prices.index.equals(target.index) or len(prices) < 2:
        raise ValueError("Price/target clocks differ or empty")
    if not np.isfinite(target).all() or target.iloc[-1] != 0:
        raise ValueError("Nonfinite or unclosed target")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0:
        raise ValueError("Invalid cost")
    left = prices.to_numpy(float)[:-1]
    right = prices.to_numpy(float)[1:]
    position = target.to_numpy(float)[:-1]
    turns = np.abs(np.diff(np.r_[0.0, target.to_numpy(float)]))
    valid = np.isfinite(left) & np.isfinite(right) & (left > 0) & (right > 0)
    if ((position != 0) & ~valid).any() or (
        (turns > 0) & (~np.isfinite(prices.to_numpy(float)) | (prices.to_numpy(float) <= 0))
    ).any():
        raise ValueError("Missing realized price during position or turnover; no fill")
    gross = np.zeros(len(target))
    active = position != 0
    gross[:-1][active] = position[active] * np.log(right[active] / left[active]) * 1e4
    cost = turns * round_trip_cost_bps / 2
    cumulative = np.cumsum(gross - cost) / 100
    peak = np.maximum.accumulate(np.r_[0, cumulative])[1:]
    # Curve is indexed by interval START; PnL at t covers [t,t+1].
    return pd.DataFrame(
        {
            "target": target,
            "gross_bps": gross,
            "cost_bps": cost,
            "net_bps": gross - cost,
            "turnover": turns,
            "cumulative_log_pct": cumulative,
            "drawdown_log_pct": cumulative - peak,
            "illustrative_equity": np.exp(cumulative / 100),
        },
        index=target.index,
    )


def trades_from_curve(curve, prices):
    p = curve.target.to_numpy()
    changes = np.flatnonzero(np.diff(np.r_[0, p]) != 0)
    trades = []
    first = None
    for index in changes:
        if first is not None:
            weight = p[first]
            segment = curve.iloc[first:index]
            # A reversal's cost is decomposed into closing old and opening new.
            exit_cost = (
                abs(weight) * curve.cost_bps.iloc[index] / max(curve.turnover.iloc[index], 1e-30)
            )
            entry_cost = (
                abs(weight) * curve.cost_bps.iloc[first] / max(curve.turnover.iloc[first], 1e-30)
            )
            gross = float(segment.gross_bps.sum())
            trades.append(
                {
                    "entry": curve.index[first],
                    "exit": curve.index[index],
                    "side": "long" if weight > 0 else "short",
                    "target": weight,
                    "entry_price": prices.iloc[first],
                    "exit_price": prices.iloc[index],
                    "gross_bps": gross,
                    "cost_bps": entry_cost + exit_cost,
                    "net_bps": gross - entry_cost - exit_cost,
                    "duration_minutes": (curve.index[index] - curve.index[first]).total_seconds()
                    / 60,
                }
            )
            first = None
        if p[index] != 0:
            first = index
    if first is not None:
        raise ValueError("Unclosed trade")
    return pd.DataFrame(
        trades,
        columns=[
            "entry",
            "exit",
            "side",
            "target",
            "entry_price",
            "exit_price",
            "gross_bps",
            "cost_bps",
            "net_bps",
            "duration_minutes",
        ],
    )
