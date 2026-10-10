"""Daily cross-asset adaptation with a common pooled model and frozen config."""

import hashlib
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from quantito.research.strategies.wristwatch.data import canonical_members, read_daily
from quantito.research.strategies.wristwatch.execution import account, trades_from_curve
from quantito.research.strategies.wristwatch.report import metrics, write_json
from quantito.research.strategies.wristwatch.signal import FEATURES, daily_features, make_model

MAPPING = {
    "experiment_name": "wristwatch_daily_cross_asset_adaptation",
    "source_30min_bar": "one trading-day observation",
    "source_60min_vwap_sigma": "two prior daily observations; sample std of 2 log returns",
    "1h_4h_1d_1w_returns": "2/8/48/336 prior trading observations",
    "4h_1d_vwap": "8/48 prior trading observations; close*volume proxy, not true traded VWAP",
    "daily_range": "48 prior observations high/low",
    "2h_hold": "4 trading observations; entry one observation after decision",
    "hour_seasonality": "disabled: sin=0, cos=1; daily dates have no intraday timestamp",
    "weekday": "weekday of date label; no execution session claim",
    "refit": "pooled expanding annual model; labels must exit before Jan 1",
    "gate": "one global prior-90-calendar-day fitted-score q80, no per-symbol tuning",
    "training_sample": "up to 40 deterministically sampled historical rows per symbol/year refit",
    "calendar": "development through 2012, validation 2013-2014, retrospective evaluation 2015-2017",
    "reason_for_calendar": "ZIP ends in 2017; 2023-2026 unavailable",
    "scope": "Hypothesis adaptation, not literal BTC reproduction; no per-symbol optimization",
}


def daily_target(index, scores, config):
    result = pd.Series(0.0, index=index)
    for timestamp, row in scores.loc[scores.target.ne(0)].iterrows():
        decision = index.get_loc(timestamp)
        entry = decision + config.daily_delay_bars
        exit_index = entry + config.hold_bars
        if exit_index >= len(index) or index[exit_index].year != timestamp.year:
            continue
        if result.iloc[entry:exit_index].ne(0).any():
            raise ValueError("Daily overlap")
        result.iloc[entry:exit_index] = row.target
    return result


def run_daily(dataset, output, config, *, years=range(2013, 2018)):
    out = Path(output)
    cache = Path(tempfile.mkdtemp(prefix="quantito-wristwatch-daily-"))
    cache.mkdir(parents=True, exist_ok=True)
    write_json(out / "leandro_parameter_mapping.json", MAPPING)
    # Save BEFORE looking at returns or fitting any model.
    write_json(
        out / "daily_frozen_config.json",
        {"config_hash": config.digest, "years": list(years), **MAPPING},
    )
    train_parts = {year: [] for year in years}
    gates = {year: [] for year in years}
    eligible = []
    groups = {}
    rejected = []
    with zipfile.ZipFile(dataset) as archive:
        members, _ = canonical_members(archive)
        for i, member in enumerate(members):
            symbol = Path(member.filename).stem
            groups[symbol] = "ETF" if "ETFs/" in member.filename else "Stock"
            try:
                bars = read_daily(archive, member)
                features = daily_features(bars)
                # Preserve chronology and valid future TRAINING labels only. Evaluation uses features alone.
                h = config.hold_bars
                outcomes = np.log(bars.open.shift(-h) / bars.open) * 1e4
                exits = bars.index.to_series().shift(-h)
                features["outcome_bps"] = outcomes
                features["label_exit"] = exits
                features["open"] = bars.open
                features["aligned"] = np.arange(len(bars)) % h == 0
                features.to_parquet(cache / f"{symbol}.parquet")
                eligible.append(symbol)
                for year in years:
                    cutoff = pd.Timestamp(f"{year}-01-01", tz="UTC")
                    train = features.loc[
                        features.aligned
                        & (features.label_exit < cutoff)
                        & features[[*FEATURES, "outcome_bps"]].notna().all(axis=1)
                    ]
                    if len(train) < 50:
                        continue
                    # Symbol-stable sample, chosen without inspecting realized metrics.
                    seed = int(
                        hashlib.sha256(f"{config.seed}/{symbol}/{year}".encode()).hexdigest()[:8],
                        16,
                    )
                    sample = train.sample(n=min(40, len(train)), random_state=seed)
                    train_parts[year].append(sample[[*FEATURES, "outcome_bps"]])
                    recent = train.loc[train.index >= cutoff - pd.Timedelta(days=90), FEATURES]
                    if len(recent):
                        gates[year].append(recent)
            except (ValueError, pd.errors.EmptyDataError) as exc:
                rejected.append({"symbol": symbol, "reason": str(exc)})
            if i % 1000 == 0:
                print(f"daily preparation {i}/{len(members)}", flush=True)
    models = {}
    fit_records = []
    for year in years:
        if not train_parts[year] or not gates[year]:
            raise ValueError(f"Insufficient pooled data for {year}")
        train = pd.concat(train_parts[year])
        gate_rows = pd.concat(gates[year])
        low, high = np.quantile(train.outcome_bps, [0.01, 0.99])
        model = make_model(len(train), config)
        model.fit(train[FEATURES], train.outcome_bps.clip(low, high))
        gate = float(np.quantile(np.abs(model.predict(gate_rows)), config.gate_quantile))
        models[year] = (model, gate)
        fit_records.append(
            {"year": year, "rows": len(train), "gate_rows": len(gate_rows), "gate_bps": gate}
        )
        print(f"daily pooled fit {year} {len(train)} rows", flush=True)
    write_json(out / "daily_fit_records.json", fit_records)
    del train_parts, gates
    records = []
    daily_returns = []
    bh_returns = []
    breakdown = []
    for i, symbol in enumerate(eligible):
        table = pd.read_parquet(cache / f"{symbol}.parquet")
        scores = []
        for year, (model, gate) in models.items():
            evaluate = table.loc[
                (table.index.year == year) & table.aligned & table[FEATURES].notna().all(axis=1)
            ]
            if evaluate.empty:
                continue
            prediction = model.predict(evaluate[FEATURES])
            scores.append(
                pd.DataFrame(
                    {
                        "target": np.where(
                            np.abs(prediction) >= gate, np.sign(prediction) * config.target, 0
                        )
                    },
                    index=evaluate.index,
                )
            )
        if not scores:
            records.append(
                {
                    "symbol": symbol,
                    "status": "NO_ELIGIBLE_EVALUATION",
                    "available_start": str(table.index[0].date()),
                    "available_end": str(table.index[-1].date()),
                    "observations": len(table),
                }
            )
            continue
        prices = table.open.loc[table.index.year.isin(years)]
        target = daily_target(table.index, pd.concat(scores), config).reindex(prices.index)
        curve = account(prices, target, config.round_trip_cost_bps)
        trades = trades_from_curve(curve, prices)
        row = {
            "symbol": symbol,
            "status": "COMPLETE",
            "available_start": str(table.index[0].date()),
            "available_end": str(table.index[-1].date()),
            "available_observations": len(table),
            **metrics(curve, trades),
        }
        # Daily market uses 252 sessions annualization; replace calendar-day Sharpe/CAGR interpretation.
        sessions = curve.net_bps / 1e4
        row["sharpe_daily_log"] = (
            float(sessions.mean() / sessions.std() * np.sqrt(252)) if sessions.std() > 0 else None
        )
        bh_target = pd.Series(1.0, index=prices.index)
        bh_target.iloc[-1] = 0
        bh_curve = account(prices, bh_target, config.round_trip_cost_bps)
        row["buy_hold_net_log_pct"] = float(bh_curve.net_bps.sum() / 100)
        row["cash_log_pct"] = 0.0
        for cost in (0, 5, 10, 20):
            row[f"net_{cost}bp_log_pct"] = float(
                (curve.gross_bps.sum() - curve.turnover.sum() * cost / 2) / 100
            )
        for side in ("long", "short"):
            row[f"{side}_net_log_pct"] = float(
                trades.loc[trades.side == side, "net_bps"].sum() / 100
            )
        records.append(row)
        daily_returns.append(curve.net_bps.rename(symbol))
        bh_returns.append(bh_curve.net_bps.rename(symbol))
        for year, block in curve.groupby(curve.index.year):
            breakdown.append(
                {
                    "symbol": symbol,
                    "year": year,
                    "net_log_pct": float(block.net_bps.sum() / 100),
                    "turnover": float(block.turnover.sum()),
                }
            )
        if i % 1000 == 0:
            print(f"daily evaluation {i}/{len(eligible)}", flush=True)
    frame = pd.DataFrame(records)
    frame["group"] = frame.symbol.map(groups)
    frame.to_csv(out / "leandro_cross_asset_metrics.csv", index=False)
    pd.DataFrame(rejected).to_csv(out / "leandro_rejected_symbols.csv", index=False)
    pd.DataFrame(breakdown).to_csv(out / "leandro_annual_stability.csv", index=False)
    # Fixed equal starting allocations across all evaluated symbols; missing history is cash,
    # not redistribution to symbols that survived or happened to be available that day.
    matrix = pd.concat(daily_returns, axis=1).fillna(0)
    buy_hold = pd.concat(bh_returns, axis=1).reindex(matrix.index).fillna(0)
    combined = pd.DataFrame(
        {
            "strategy_equal_weight_bps": matrix.mean(axis=1),
            "buy_hold_equal_weight_bps": buy_hold.mean(axis=1),
            "cash_bps": 0,
        }
    )
    combined.to_csv(out / "leandro_equal_weight_curve.csv")
    complete = frame.loc[frame.status == "COMPLETE"]
    returns = complete.net_additive_log_pct
    complete.groupby("group").agg(
        symbols=("symbol", "count"),
        mean_net_log_pct=("net_additive_log_pct", "mean"),
        median_net_log_pct=("net_additive_log_pct", "median"),
        profitable_fraction=("net_additive_log_pct", lambda values: values.gt(0).mean()),
    ).to_csv(out / "leandro_group_summary.csv")
    absolute = returns.abs().sort_values(ascending=False)
    summary = {
        "evaluated_symbols": len(complete),
        "no_evaluation": int(frame.status.ne("COMPLETE").sum()),
        "rejected": len(rejected),
        "profitable_fraction": float(returns.gt(0).mean()),
        "median_net_log_pct": float(returns.median()),
        "mean_net_log_pct": float(returns.mean()),
        "equal_weight_net_log_pct": float(combined.strategy_equal_weight_bps.sum() / 100),
        "buy_hold_equal_weight_net_log_pct": float(combined.buy_hold_equal_weight_bps.sum() / 100),
        "top_10_absolute_pnl_share": float(absolute.head(10).sum() / absolute.sum()),
        "best_descriptive_only": complete.nlargest(5, "net_additive_log_pct")[
            ["symbol", "net_additive_log_pct"]
        ].to_dict("records"),
        "worst_descriptive_only": complete.nsmallest(5, "net_additive_log_pct")[
            ["symbol", "net_additive_log_pct"]
        ].to_dict("records"),
        "warning": "Daily hypothesis adaptation; unknown adjustments/delistings, hindsight universe, hypothetical shorting. Not BTC reproduction or evidence of tradable alpha.",
    }
    write_json(out / "leandro_cross_asset_summary.json", summary)
    (out / "leandro_cross_asset_summary.md").write_text(
        "# Daily cross-asset adaptation\n\n"
        + summary["warning"]
        + "\n\n```json\n"
        + pd.Series(summary).to_json(indent=2)
        + "\n```\n"
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    (combined.cumsum() / 100).plot(ax=axes[0])
    axes[0].set_ylabel("Additive log PnL (%)")
    axes[1].hist(returns, bins=60)
    axes[1].set_xlabel("Net log PnL per symbol (%)")
    fig.tight_layout()
    fig.savefig(out / "leandro_equity_curves.png", dpi=130)
    plt.close(fig)
    return summary
