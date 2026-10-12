"""Recovered HGB signal. Features use only observations strictly before t."""

from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from quantito.research.strategies.wristwatch.config import Config

FEATURES = [
    "z60",
    "sigma60_bps",
    "prior_return_1h_bps",
    "prior_return_4h_bps",
    "prior_return_1d_bps",
    "prior_return_1w_bps",
    "prior_vwap_4h_gap_bps",
    "prior_vwap_1d_gap_bps",
    "prior_4h_log_quote_volume",
    "prior_1d_range_bps",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
]


class SignalModel(Protocol):
    def fit(self, x, y): ...
    def predict(self, x): ...


def make_model(rows, config):
    # Preserve source auto early stopping; log library versions for parity.
    return HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.05,
        max_iter=config.max_iter,
        max_leaf_nodes=7,
        min_samples_leaf=max(20, rows // 100),
        l2_regularization=10.0,
        random_state=config.seed,
    )


def build_features(panel):
    complete = panel.bar_complete.astype(bool)
    prior = panel.prior_close
    frame = pd.DataFrame(index=panel.index)
    frame["z60"] = panel.z60
    frame["sigma60_bps"] = panel.sigma60 * 1e4
    for name, steps in (("1h", 2), ("4h", 8), ("1d", 48), ("1w", 336)):
        frame[f"prior_return_{name}_bps"] = np.log(prior / prior.shift(steps)) * 1e4
    for name, steps in (("4h", 8), ("1d", 48)):
        volume = panel.volume.where(complete).rolling(steps, min_periods=steps).sum().shift(1)
        quote = panel.quote_volume.where(complete).rolling(steps, min_periods=steps).sum().shift(1)
        frame[f"prior_vwap_{name}_gap_bps"] = (
            prior / (quote / volume.where(volume.gt(0))) - 1
        ) * 1e4
    quote = panel.quote_volume.where(complete).rolling(8, min_periods=8).sum().shift(1)
    frame["prior_4h_log_quote_volume"] = np.log1p(quote)
    high = panel.high.where(complete).rolling(48, min_periods=48).max().shift(1)
    low = panel.low.where(complete).rolling(48, min_periods=48).min().shift(1)
    frame["prior_1d_range_bps"] = (high / low - 1) * 1e4
    hour = panel.index.hour + panel.index.minute / 60
    frame["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    frame["weekday_sin"] = np.sin(2 * np.pi * panel.index.dayofweek / 7)
    frame["weekday_cos"] = np.cos(2 * np.pi * panel.index.dayofweek / 7)
    return frame.replace([np.inf, -np.inf], np.nan)


def daily_features(bars):
    """Explicit ordinal mapping: 1 source 30m bar -> 1 trading-day observation.

    Minute z60/sigma60 -> previous 2 daily observations; true quote volume
    unavailable, use close*volume proxy. UTC hour seasonality is disabled.
    """
    panel = bars.copy()
    panel["bar_complete"] = True
    panel["prior_close"] = panel.close.shift(1)
    panel["quote_volume"] = panel.close * panel.volume
    sigma = np.log(panel.close / panel.close.shift()).rolling(2, min_periods=2).std().shift(1)
    volume = panel.volume.rolling(2, min_periods=2).sum().shift(1)
    quote = panel.quote_volume.rolling(2, min_periods=2).sum().shift(1)
    panel["sigma60"] = sigma
    panel["z60"] = (panel.prior_close - quote / volume.where(volume.gt(0))) / (
        sigma * panel.prior_close
    )
    return build_features(panel)


def label_table(panel, features, config):
    h = config.hold_bars
    outcome = np.log(panel.open.shift(-h) / panel.open) * 1e4
    complete = panel.bar_complete.astype(int).rolling(h, min_periods=h).sum().shift(-(h - 1)).eq(h)
    aligned = (panel.index.hour % 2 == 0) & (panel.index.minute == 0)
    table = features.loc[aligned & features.notna().all(axis=1)].copy()
    table["outcome_bps"] = outcome.reindex(table.index).where(complete.reindex(table.index))
    return table


def fit_scores(panel, config=None, *, variants=("jan_refit_train90",), years=None):
    config = config or Config()
    features = build_features(panel)
    table = label_table(panel, features, config)
    years = list(years or range(2018, panel.index[-1].year + 1))
    predictions = []
    fits = []
    for year in years:
        start = pd.Timestamp(f"{year}-01-01", tz="UTC")
        end = start + pd.DateOffset(years=1)
        for variant in variants:
            if variant not in ("jan_refit_train90", "aug_fixed_postfit", "oct_refit_postfit"):
                raise ValueError("Unspecified variant")
            cutoff = (
                start
                if variant.startswith("jan")
                else pd.Timestamp(
                    f"{year - 1}-{'08-03' if variant.startswith('aug') else '10-01'}", tz="UTC"
                )
            )
            exits = table.index + pd.Timedelta(minutes=30 * config.hold_bars)
            train = table.loc[(exits < cutoff) & table.outcome_bps.notna()]
            evaluate = table.loc[(table.index >= start) & (table.index < end)]
            if len(train) < 200 or evaluate.empty:
                continue
            low, high = np.quantile(train.outcome_bps, [0.01, 0.99])
            model = make_model(len(train), config)
            model.fit(train[FEATURES], train.outcome_bps.clip(low, high))
            gate_rows = (
                train.loc[train.index >= cutoff - pd.Timedelta(days=90)]
                if variant.startswith("jan")
                else table.loc[(table.index >= cutoff + pd.Timedelta(days=1)) & (exits < start)]
            )
            if len(gate_rows) < 200:
                raise ValueError("Insufficient prior gate context")
            gate = float(
                np.quantile(np.abs(model.predict(gate_rows[FEATURES])), config.gate_quantile)
            )
            if not np.isfinite(gate) or gate <= 0:
                raise ValueError("Invalid gate")
            forecast = model.predict(evaluate[FEATURES])
            current = pd.DataFrame(
                {
                    "prediction_bps": forecast,
                    "gate_bps": gate,
                    "target": np.where(
                        np.abs(forecast) >= gate, np.sign(forecast) * config.target, 0
                    ),
                    "variant": variant,
                    "fit_cutoff": cutoff.isoformat(),
                },
                index=evaluate.index,
            )
            predictions.append(current)
            fits.append(
                {
                    "year": year,
                    "variant": variant,
                    "fit_cutoff": cutoff.isoformat(),
                    "last_label_exit": (
                        train.index[-1] + pd.Timedelta(minutes=30 * config.hold_bars)
                    ).isoformat(),
                    "train_rows": len(train),
                    "gate_rows": len(gate_rows),
                    "gate_bps": gate,
                    "winsor_low_bps": float(low),
                    "winsor_high_bps": float(high),
                }
            )
            print(f"fit {year} {variant} rows={len(train)}", flush=True)
    if not predictions:
        raise ValueError("Insufficient training/evaluation data")
    return pd.concat(predictions), fits
