# Wristwatch BTC 2-hour POC

Research only. No strategy is registered in the FastAPI production registry. All
code is packaged under `quantito.research.strategies.wristwatch` in the current
`src/quantito` layout. `quantito-pipe` and `quantito-engine` are not modified.
This is the BTC 2h research lead from the October 10 brief, distinct from the live
Wristwatch implementation.

## Recovered specification

The brief's chart generator links to `run_btc_multihorizon_is_2017_2024.py`,
`run_btc_2h_expanding_is_walkforward.py`,
`run_btc_2h_intermediate_robustness.py` and minute repricing scripts in the local
`wristwatch_1m_research_20260922` study. Input/source hashes are recorded per run;
that external study is an input, not an import dependency.

At UTC times 00:00, 02:00, ..., predict a 2-hour open-to-open log return in bps.
The regressor is sklearn HistGradientBoostingRegressor: squared error, learning
rate 0.05, 100 iterations, 7 leaves, min leaf max(20, train rows // 100), L2 10,
seed 432 and sklearn's default automatic early stopping. Training outcomes are
winsorized at their training-only 1st and 99th percentiles.

Fourteen features are used. All price/volume inputs precede the decision:

- z60 = (previous minute close - previous 60-minute VWAP) /
  (previous 60-minute sample standard deviation of minute log returns * previous close).
- sigma60 in bps.
- prior log returns over 1h, 4h, 1d and 1w (2, 8, 48, 336 30-minute bars).
- prior close gaps versus 4h and 1d traded VWAP.
- log(1 + prior 4h quote volume).
- prior 1d high/low range in bps.
- sine/cosine of UTC hour and weekday.

Select if |prediction| >= gate; target = sign(prediction) * 0.15. **0.15 is
fractional signed account exposure, not a score threshold.** Hold 120 minutes;
no overlapping sleeves. Consecutive identical signed targets are netted; there
is no artificial exit/re-entry cost. Reversals pay on the entire signed target
change. Holds that do not fit the known split/year end are excluded.

Annual January refits train on expanding observations from September 2017 with
label exits strictly before Jan 1. Gate is q80 of absolute fitted scores over
prior 90 calendar days. The long chart starts Jan 2018, ends Aug 3 2024 exclusive.
The size and policy were selected retrospectively, so this is not pristine OOS.

The brief's 2025 variants are:

| Variant | Fit cutoff | Gate |
| --- | --- | --- |
| aug_fixed_postfit | Aug 3 of preceding year | q80 on postfit rows from cutoff+1 day through label exits before Jan 1 |
| oct_refit_postfit | Oct 1 of preceding year | same postfit rule |
| jan_refit_train90 | Jan 1 of evaluation year | prior 90 training calendar days |

2025 evaluates Jan 2 through Jan 1 2026 exclusive. October was introduced after
inspecting 2025 results. All three remain retrospective diagnostics. For 2026,
apply the same declared annual schedules using only previous-year labels; record
config hash before simulation and never describe already inspected data as fresh.

## Execution and PnL

Default delay is exactly one minute: t+1 minute Binance spot open, exit after
120 minutes. Zero delay is explicitly an optimistic sensitivity control.
Gross bps per interval = signed target * log(next open / current open) * 10,000.
Cost = |target - previous target| * round_trip_cost_bps / 2.
Default 5 bps round trip means 2.5 per side; entry+exit of target .15 costs .75
account bps. The code uses account target turnover, not portfolio one-way
CASH-inclusive turnover; the unpublished long-only portfolio contracts do not
apply to signed BTC positions.

The reported +25.89% / -9.67% are **additive weighted log PnL and log drawdown**.
They are not conventional compounded portfolio return / drawdown. The reports
also show separately labeled exponential illustrations; those do not establish
a self-financing spot/short account. Borrow, funding, spread, slippage, liquidity,
collateral, dividends, interest and actual fills are absent. CAGR is illustrative
and omitted for periods shorter than a year. Sharpe uses daily log PnL and 365.25
for BTC; daily equities use observation returns and 252.

## Causality correction and reference replay

The source scripts filter evaluated decisions using future label availability
and completeness of the following bars. The regenerated candidate does **not**
filter decisions by future realized prices: only feature availability and known
calendar boundaries. Missing realized prices while invested cause explicit
failure; prices are never filled. This can change selected decisions relative to
the chart even when the model is identical. A separate frozen-target replay can
compare the exact saved targets to the brief, but carries their selection caveat.
Do not confuse frozen-target repricing with full signal/model reproduction.

Features and annual refits have metamorphic tests: mutating all later prices
cannot change an earlier decision or fitted gate. Regimes use prior-day 20-day
trend relative to 20-day volatility; volatility thresholds are expanding past
medians. UTC sessions are 00–08, 08–16, 16–24. Regime/session attribution is
explanatory and must not be used to select profitable subgroups after the fact.

## Reproduction

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,research]'
export OMP_NUM_THREADS=1
export MPLCONFIGDIR=/tmp/quantito-matplotlib
.venv/bin/python -m quantito.research.strategies.wristwatch \
  --experiment download --binance-dir /tmp/quantito-wristwatch-data \
  --first-month 2017-09 --last-month 2026-09
.venv/bin/python -m quantito.research.strategies.wristwatch \
  --experiment btc --binance-dir /tmp/quantito-wristwatch-data \
  --panel-dir /path/to/btc_causal_1m_features_2017_2024 \
  --panel-dir /path/to/btc_causal_1m_features_postcut_2024_2025 \
  --reference-dir /path/to/wristwatch_1m_research_20260922/output
.venv/bin/python -m quantito.research.strategies.wristwatch \
  --experiment daily-cross-asset --dataset ~/Downloads/archive.zip \
  --daily-label-mode execution_aligned \
  --output artifacts/wristwatch/daily_revision/execution_aligned
.venv/bin/python -m quantito.research.strategies.wristwatch \
  --experiment daily-cross-asset --dataset ~/Downloads/archive.zip \
  --daily-label-mode source_label_emulation \
  --output artifacts/wristwatch/daily_revision/source_label_emulation
.venv/bin/python -m pytest -q
.venv/bin/python -m unittest discover tests
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check
```

The historical reproduction requires the original causal panels and, optionally,
the frozen targets as explicit external inputs; this PR does not distribute them
or claim that a clean clone contains the original dataset. Their upstream raw
feature construction is implemented by `resample_minutes` and `build_features`,
but monthly warmup/parity of a complete rebuilt historical panel needs independent
certification. Official recent BTC data is rebuilt without these external panels.

Results go to ignored `artifacts/wristwatch/`: config, data hashes, scores, fits,
metrics, trades, minute equity/drawdown parquet, daily CSV, attribution CSV, JSON,
Markdown and PNG plots. Data ZIPs and daily feature caches stay outside Git.
The daily feature cache is owned by `TemporaryDirectory`: it is removed when the
run returns or raises, including failures after parquet files have been written.
Successful and exceptional cleanup are checked using synthetic datasets.
`execution_aligned` is the daily default/principal label t+1→t+5;
`source_label_emulation` is comparison-only t→t+4. Execution remains t+1→t+5
in both modes, and annual training excludes the actual label exit at/after cutoff.
Use separate output paths as above to retain both modes and config hashes.
The default sensitivity matrix covers costs 0/5/10 bps and delay 0/1/2/5 minutes;
CLI target/cost/delay overrides permit declared reruns. Other frequencies, target
sizes or refit dates must be declared before evaluation and archived under distinct
output paths; no winner is selected automatically.

## Continuous integration

`.github/workflows/research-quality.yml` runs Python 3.12 installation with
`.[dev,research]`, pytest, Ruff lint/format and `git diff --check` on PRs and
pushes to this branch. Tests use synthetic fixtures and no external datasets or
HTTP downloads. `QUANTITO_OFFLINE_TESTS=1` explicitly skips the existing Docker
build smoke test because its dependency installation can require network; the
Docker artifact checks still run and the integration smoke remains available
outside offline mode. Run the same offline suite locally with:

```sh
QUANTITO_OFFLINE_TESTS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q
```

## Promotion gates

First establish data rights, point-in-time coverage and source/raw-feature parity.
Then certify causal decision generation, missing-data treatment, executable
long/short accounting and realistic costs. Freeze a protocol and reserve a truly
unseen period. Require stable year/side/regime/session performance and reasonable
multiple-testing controls. Only then design a separate stateless evaluation API
adapter and a versioned model contract; engine may orchestrate and dispatch the
validated algorithm in a later PR. This POC is not approved for execution.
