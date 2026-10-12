# Daily signal and dataset diagnostics

Research continuation of Draft PR #14. Execution comparison (passive, active and
hybrid) is deferred. The price assumption remains next-bar opens, with hypothetical
shorts and additive target-weighted log accounting. Zero cost is a diagnostic of
the signal; it does not establish zero commissions, fills or execution costs.

## Frozen protocol

Principal mode: `execution_aligned`, label t+1 to t+5. Original HGB parameters,
seed 432, annual pooled fit, global score gate, target 0.15 and entire eligible
universe are retained. Development through 2012, validation 2013–2014 and
retrospective evaluation 2015–2017. All dates have already been inspected.
The diagnostic protocol is saved before fitting and before final metrics.

Signals are generated once. Comparisons apply deterministic changes to the same
target sequence, never new fitted models or per-symbol parameter selection:

| Scenario | Position | Purpose |
| --- | --- | --- |
| long_short | Original signed target | Principal signal |
| long_only | Positive original targets; otherwise cash | Long contribution |
| short_only | Negative original targets; otherwise cash | Hypothetical short contribution |
| long_same_windows | Absolute value of original target | Same absolute exposure and holding intervals, always long |
| buy_hold_15pct | Constant +0.15 over available evaluation history, terminal exit | Comparable maximum exposure; different time exposure |
| cash | Zero | Zero-return control; no cash interest assumed |

Costs 0 and 5 bps round trip use identical gross returns and target turnover.
Consecutive positions net normally. Direction reversals can cost more than the
always-long control; that is disclosed by computing turnover per scenario.
Equal weighting reserves fixed 1/N capital for every evaluated instrument, even
if it has zero trades or missing history. Missing history stays cash. Group
results use fixed group denominators and the common observed-date calendar.
Sharpe uses 252 over observed date labels, without certifying a trading calendar.
Yearly drawdowns reset at the year boundary; full-period drawdown is separate.

## Quality annotations

Inspect every valid history, including those without eligible evaluation:

- Absolute log close/close, open/previous-close and next-open/current-open moves
  greater than log(1.4). This is a symmetric price-ratio threshold, not a claim
  that an action occurred. It includes drops beyond 1/1.4.
- Zero volume, at least five identical consecutive closes and calendar gaps
  greater than seven days. Calendar gaps can reflect suspensions, holidays or
  missing observations; no exchange calendar is supplied.
- Available start/end and histories ending before the archive's final date.
  An early end is not evidence of a confirmed delisting or terminal payoff.

Flags do not repair, remove or winsorize any row. Forward flags annotate realized
intervals only: their PnL contribution is an ex-post data-quality diagnostic,
never a signal input, training filter or investable exclusion rule. Metadata is
insufficient to establish splits/dividends, adjustment conventions, point-in-time
prices, delistings or licensing. Those limitations remain unresolved.

Concentration is reported against explicit absolute/positive PnL denominators,
with top ten and top 1% shares. No winner/loser is removed to improve performance.
Annual and Stock/ETF group results distinguish temporal consistency from average
return. No sector labels are invented.

## Reproduction and artifacts

```sh
OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/quantito-matplotlib \
  .venv/bin/python -m quantito.research.strategies.wristwatch \
  --experiment daily-cross-asset --dataset ~/Downloads/archive.zip \
  --daily-label-mode execution_aligned \
  --output artifacts/wristwatch/daily_diagnostics_2026-10-12
QUANTITO_OFFLINE_TESTS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check
```

The normal daily run now writes `diagnostics/` with protocol, quality-per-symbol,
per-symbol scenario metrics, annual-per-symbol metrics, aggregated annual/scenario
comparisons, equal-weight curves and a PNG. All large run artifacts are ignored.
Only small aggregate results and documentation are committed. Feature caches
still use TemporaryDirectory and are removed on success or exception. Tests use
synthetic data only and check exact exposure, reconciliation across sides/costs,
missing-history-as-cash weighting, quality annotations and concentration arithmetic.

## Decision after this diagnostic

Inspect data issues and result stability before requesting an updated dataset.
The next execution study should declare limit-price placement, timeout, fills,
partials, cancellations and exit rules before comparing passive, active and
hybrid policies. Daily OHLCV cannot validate queue position or guaranteed fills.
Operational implementation remains outside this research candidate.
