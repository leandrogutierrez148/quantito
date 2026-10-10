# Leandro dataset and BTC data audit

`archive.zip`: 515,591,518 bytes; SHA-256
`d9317c8fb2d63b9b00db5f933b6c9639d2bf7ea3b918169bb5cec5903dce85a1`.
17,078 TXT files, 1,618,046,652 uncompressed bytes. The `Data/Stocks` /
`Data/ETFs` and `Stocks` / `ETFs` trees mirror each other byte-for-byte;
SHA-256 checks reduce them to 8,539 unique instruments. Never count mirrors twice.

Every nonempty file has daily date labels and the seven columns
`Date,Open,High,Low,Close,Volume,OpenInt`. No BTC/minute data, README, license,
sectors, corporate actions or adjustment metadata exists. `ebtc.us` is an equity
symbol, not BTC cryptocurrency. The format resembles public Stooq/Kaggle stocks,
but provider and licensing cannot be authenticated from this ZIP.

Valid history: Jan 2 1962 through Nov 10 2017. 8,431 valid instruments:
7,105 stocks and 1,326 ETFs. Reject 108 files: 32 empty, 39 invalid/nonpositive or
nonfinite OHLCV, 21 invalid highs, 16 invalid lows. Do not silently repair them.
OpenInt is always zero in nonempty files. No duplicate dates were found in the
valid files. Weekends and exchange holidays are expected; gaps greater than four
calendar days are reported without claiming an exchange-calendar validation.
Some symbols end before the common final date; delisting status/returns cannot be
established. A static archive can contain survivorship bias even with such files.

Date labels are localized to UTC for deterministic storage. They do not say when
a US session opened; no intraday/session inference is made. Split and dividend
adjustments, point-in-time revisions and volume conventions are unknown.
The universe cannot validate BTC's literal 2-hour hypothesis, but is used for the
mandatory separate daily cross-asset hypothesis adaptation.

## Declared daily experiment

`wristwatch_daily_cross_asset_adaptation` maps one 30-minute source bar to one
trading-day observation. Two-hour holds become four observations, and execution
moves at least one observation after the decision. Minute z60/sigma becomes two
prior observations. Return/VWAP/range windows map to the original 2/8/48/336 bar
counts. True quote volume is absent, so close*volume is an explicit proxy. UTC
hour terms are disabled and weekday terms use date labels. This is not the same
economic horizon and not a literal reproduction.

Configuration is common across the universe: target .15, HGB family/seed/gate,
annual expanding refits, no individual retrospective parameter selection.
Models are pooled cross-sectionally; each refit samples at most 40 prior rows per
symbol deterministically, with a global prior-90-day score gate. This is an
additional declared computational adaptation, not the BTC per-asset fit.
Development ends in 2012; validation is 2013–14; subsequent retrospective
assessment is 2015–17, with 2017 partial. All dates are frozen before results.
No 2023–26 equity evaluation is possible from this archive.

All valid symbols are attempted; short histories without 336-bar warmup are
reported as ineligible. Equal-weight results allocate fixed equal capital to all
evaluated symbols and leave missing history as cash, avoiding daily survivor
redistribution. Best/worst symbols are descriptive only. Costs 0/5/10/20 bps are
reported without selecting a winner. ETFs/stocks are groups; sectors cannot be
invented. Borrow availability, terminal delisting payouts and corporate actions
remain unresolved, so positive results would not establish executable alpha.

## BTC source

Use independently downloaded official Binance **spot BTCUSDT 1m** ZIPs. URLs,
source coverage and SHA-256 hashes are saved. Each archive is compared to its
published `.CHECKSUM` and rechecked at load time. TLS remains verified. No API
keys, paid services, EODHD or BigQuery jobs are used.

The official [Binance public data documentation](https://github.com/binance/binance-public-data)
specifies OHLCV and quote volume, UTC epoch milliseconds before 2025 and
microseconds from Jan 1 2025, plus checksum files. The loader supports both units.
Gaps, duplicate/off-minute timestamps, invalid candles and conflicting source
panels are explicit errors or coverage records. No silent exchange mixing.

Original features through 2025 come from persisted local Binance-derived panels;
recent features come from the official minute series. Compare overlapping opens
against local sources before treating the two provenance segments as equivalent.
The reproduced metric table and source manifests carry any discrepancies.
