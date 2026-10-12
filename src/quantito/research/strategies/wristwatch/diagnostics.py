"""Retrospective diagnostics on frozen daily signals; never select or repair data."""

from pathlib import Path

import numpy as np
import pandas as pd

from quantito.research.strategies.wristwatch.execution import account
from quantito.research.strategies.wristwatch.report import write_json

PROTOCOL = {
    "experiment": "daily_signal_quality_diagnostics",
    "signal": "label mode and effective config hash in ../daily_frozen_config.json; fits, seed, gate and universe unchanged",
    "costs_round_trip_bps": [0, 5],
    "primary_cost_bps": 0,
    "zero_cost_role": "signal diagnostic, not a forecast of free real execution",
    "jump_threshold_ratio": 1.4,
    "calendar_gap_days": 7,
    "stale_close_run_bars": 5,
    "flags": "investigation prompts, not confirmed splits, bad prices or delistings",
    "selection": "no flagged row/symbol excluded; no repair, winsorization or per-symbol tuning",
    "scenarios": [
        "long_short",
        "long_only",
        "short_only",
        "long_same_windows",
        "buy_hold_15pct",
        "cash",
    ],
    "long_same_windows": "abs(frozen signed target): identical timing and absolute exposure, always long",
    "buy_hold_15pct": "constant 0.15 during each available evaluation history, terminal exit; different time exposure",
    "weighting": "fixed 1/N across all evaluated symbols; missing history cash; group denominator fixed within group",
    "annualization": "252 over union of observed date labels; no exchange-calendar certification",
    "concentration": "descriptive top absolute/positive PnL shares; never used to select a universe",
    "forward_flags": "ex-post annotation of realized intervals, never used for signal or refit",
    "scope": "2013-2017 already inspected; static hindsight universe, unknown adjustments and delistings",
    "execution": "unchanged next-bar opens; passive/active/hybrid execution deferred",
}


def quality_flags(bars):
    """Full-history annotations. Forward columns describe realized intervals only."""
    threshold = np.log(PROTOCOL["jump_threshold_ratio"])
    changes = bars.close.ne(bars.close.shift())
    run = bars.groupby(changes.cumsum()).cumcount() + 1
    return pd.DataFrame(
        {
            "close_jump": np.log(bars.close / bars.close.shift()).abs().gt(threshold),
            "overnight_jump": np.log(bars.open / bars.close.shift()).abs().gt(threshold),
            "zero_volume": bars.volume.eq(0),
            "stale_close": run.ge(PROTOCOL["stale_close_run_bars"]),
            "calendar_gap": bars.index.to_series().diff().dt.days.gt(PROTOCOL["calendar_gap_days"]),
            "forward_open_jump": np.log(bars.open.shift(-1) / bars.open).abs().gt(threshold),
            "forward_calendar_gap": bars.index.to_series()
            .diff()
            .shift(-1)
            .dt.days.gt(PROTOCOL["calendar_gap_days"]),
        },
        index=bars.index,
    )


def scenario_targets(target, exposure=0.15):
    constant = pd.Series(exposure, index=target.index)
    constant.iloc[-1] = 0
    return {
        "long_short": target,
        "long_only": target.clip(lower=0),
        "short_only": target.clip(upper=0),
        "long_same_windows": target.abs(),
        "buy_hold_15pct": constant,
        "cash": target * 0,
    }


def concentration(values):
    absolute = values.abs().sort_values(ascending=False)
    positive = values.clip(lower=0).sort_values(ascending=False)
    return {
        "top_10_absolute_pnl_share": float(absolute.head(10).sum() / absolute.sum())
        if absolute.sum()
        else None,
        "top_1pct_absolute_pnl_share": float(
            absolute.head(max(1, int(np.ceil(len(values) * 0.01)))).sum() / absolute.sum()
        )
        if absolute.sum()
        else None,
        "top_10_positive_pnl_share": float(positive.head(10).sum() / positive.sum())
        if positive.sum()
        else None,
        "absolute_pnl_sum_pct": float(absolute.sum()),
        "positive_pnl_sum_pct": float(positive.sum()),
        "negative_pnl_sum_pct": float(values.clip(upper=0).sum()),
    }


def curve_stats(pnl_bps):
    pnl = pnl_bps / 100
    cumulative = pnl.cumsum()
    drawdown = cumulative - cumulative.cummax().clip(lower=0)
    std = pnl_bps.std()
    return {
        "net_log_pct": float(pnl.sum()),
        "max_drawdown_log_pct": float(drawdown.min()),
        "sharpe_252_observed_dates": float(pnl_bps.mean() / std * np.sqrt(252))
        if std > 0
        else None,
    }


class DailyDiagnostics:
    """Accumulate fixed-capital comparisons without caching external market data."""

    def __init__(self, output):
        self.output = Path(output) / "diagnostics"
        self.quality = []
        self.symbols = []
        self.annual_symbols = []
        self.sums = {}
        self.group_counts = {}
        self.seen = set()
        write_json(self.output / "protocol.json", PROTOCOL)

    def inspect(self, symbol, group, bars):
        flags = quality_flags(bars)
        self.quality.append(
            {
                "symbol": symbol,
                "group": group,
                "start": str(bars.index[0].date()),
                "end": str(bars.index[-1].date()),
                "observations": len(bars),
                **{name: int(flags[name].sum()) for name in flags},
            }
        )
        return flags

    def observe(self, symbol, group, prices, target, flags, exposure):
        if symbol in self.seen:
            raise ValueError(f"Duplicate diagnostic symbol: {symbol}")
        self.seen.add(symbol)
        self.group_counts[group] = self.group_counts.get(group, 0) + 1
        annotated = flags.reindex(prices.index)
        if annotated.isna().any().any():
            raise ValueError("Missing quality annotations")
        flagged = annotated.forward_open_jump | annotated.forward_calendar_gap
        for scenario, weights in scenario_targets(target, exposure).items():
            # Gross and turnover are frozen; cost sensitivities never regenerate trades.
            curve = account(prices, weights, 0)
            for cost in PROTOCOL["costs_round_trip_bps"]:
                pnl = curve.gross_bps - curve.turnover * cost / 2
                row = {
                    "symbol": symbol,
                    "group": group,
                    "scenario": scenario,
                    "cost_bps": cost,
                    "observations": len(prices),
                    "mean_abs_exposure": float(weights.abs().mean()),
                    "turnover": float(curve.turnover.sum()),
                    "flagged_gross_log_pct": float(curve.gross_bps.loc[flagged].sum() / 100),
                    "flagged_abs_gross_log_pct": float(
                        curve.gross_bps.loc[flagged].abs().sum() / 100
                    ),
                    "all_abs_gross_log_pct": float(curve.gross_bps.abs().sum() / 100),
                    **curve_stats(pnl),
                }
                self.symbols.append(row)
                for bucket in ("ALL", group):
                    key = (bucket, scenario, cost)
                    self.sums[key] = (
                        self.sums[key].add(pnl, fill_value=0) if key in self.sums else pnl.copy()
                    )
                for year, block in pnl.groupby(pnl.index.year):
                    self.annual_symbols.append(
                        {
                            "symbol": symbol,
                            "group": group,
                            "scenario": scenario,
                            "cost_bps": cost,
                            "year": year,
                            "net_log_pct": float(block.sum() / 100),
                        }
                    )

    def finish(self):
        if not self.symbols:
            raise ValueError("No evaluated diagnostic symbols")
        frame = pd.DataFrame(self.symbols)
        quality = pd.DataFrame(self.quality)
        annual_symbols = pd.DataFrame(self.annual_symbols)
        frame.to_csv(self.output / "per_symbol.csv", index=False)
        quality.to_csv(self.output / "quality_per_symbol.csv", index=False)
        annual_symbols.to_csv(self.output / "annual_per_symbol.csv", index=False)
        reports, annual, curves = [], [], []
        for (group, scenario, cost), series in sorted(self.sums.items()):
            count = len(self.seen) if group == "ALL" else self.group_counts[group]
            # The calendar is the union across all evaluated symbols, including inactive dates.
            clock = self.sums[("ALL", scenario, cost)].index
            pnl = series.reindex(clock, fill_value=0).sort_index() / count
            selected = frame.loc[(frame.scenario == scenario) & (frame.cost_bps == cost)]
            if group != "ALL":
                selected = selected.loc[selected.group == group]
            prefix = {"group": group, "scenario": scenario, "cost_bps": cost, "symbols": count}
            reports.append(
                {
                    **prefix,
                    **curve_stats(pnl),
                    "median_symbol_net_log_pct": float(selected.net_log_pct.median()),
                    "profitable_fraction": float(selected.net_log_pct.gt(0).mean()),
                    "mean_symbol_abs_exposure": float(selected.mean_abs_exposure.mean()),
                    "flagged_gross_mean_log_pct": float(selected.flagged_gross_log_pct.mean()),
                    "flagged_abs_gross_share": float(
                        selected.flagged_abs_gross_log_pct.sum()
                        / selected.all_abs_gross_log_pct.sum()
                    )
                    if selected.all_abs_gross_log_pct.sum()
                    else None,
                    **concentration(selected.net_log_pct),
                }
            )
            for year, block in pnl.groupby(pnl.index.year):
                annual.append({**prefix, "year": year, **curve_stats(block)})
            if group == "ALL":
                curves.append(pnl.rename(f"{scenario}_{cost}bp"))
        report = pd.DataFrame(reports)
        report.to_csv(self.output / "scenario_summary.csv", index=False)
        pd.DataFrame(annual).to_csv(self.output / "annual_summary.csv", index=False)
        pd.concat(curves, axis=1).to_csv(self.output / "equal_weight_curves.csv")
        write_json(
            self.output / "quality_summary.json",
            {
                "valid_symbols_inspected": len(quality),
                "evaluated_symbols": len(self.seen),
                "counts": {
                    name: {
                        "rows": int(quality[name].sum()),
                        "symbols": int(quality[name].gt(0).sum()),
                    }
                    for name in quality_flags_columns()
                },
                "histories_ending_before_archive_end": int(quality.end.lt(quality.end.max()).sum()),
                "adjustments": "unknown, flags do not certify splits or dividends",
                "delistings": "unknown, early history end does not prove delisting",
                "license": "unknown",
                "flags_used_for_signal_or_exclusion": False,
            },
        )
        self.plot()
        return report

    def plot(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        curves = pd.read_csv(self.output / "equal_weight_curves.csv", index_col=0, parse_dates=True)
        fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        for cost, ax in zip(PROTOCOL["costs_round_trip_bps"], axes, strict=True):
            selected = curves[[f"{name}_{cost}bp" for name in PROTOCOL["scenarios"]]]
            (selected.cumsum() / 100).plot(ax=ax)
            ax.set_ylabel("Additive log PnL (%)")
            ax.set_title(f"Frozen daily signals; {cost} bps round trip; hypothetical shorts")
        fig.tight_layout()
        fig.savefig(self.output / "scenario_curves.png", dpi=130)
        plt.close(fig)


def quality_flags_columns():
    return (
        "close_jump",
        "overnight_jump",
        "zero_volume",
        "stale_close",
        "calendar_gap",
        "forward_open_jump",
        "forward_calendar_gap",
    )
