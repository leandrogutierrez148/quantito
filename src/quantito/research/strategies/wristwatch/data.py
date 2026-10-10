"""Offline loaders: ZIP streaming, exact minute prices, explicit missing data."""

import hashlib
import io
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

OHLCV = ["open", "high", "low", "close", "volume"]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_bars(frame, *, minute=False):
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("UTC timestamps required")
    if str(frame.index.tz) != "UTC" or frame.index.has_duplicates:
        raise ValueError("Timestamps must be unique and UTC")
    if not frame.index.is_monotonic_increasing or frame.empty:
        raise ValueError("Bars must be nonempty and sorted")
    values = frame[OHLCV].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("Invalid OHLCV")
    if (frame.high < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("Invalid high")
    if (frame.low > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("Invalid low")
    if minute and (frame.index != frame.index.floor("min")).any():
        raise ValueError("Off-minute timestamp")
    if (
        minute
        and len(frame) > 1
        and frame.index.to_series().diff().dropna().min() < pd.Timedelta(minutes=1)
    ):
        raise ValueError("Sub-minute bars are unsupported")
    return frame


def canonical_members(archive):
    """Deduplicate directory mirrors by basename, requiring matching bytes."""
    groups = defaultdict(list)
    for info in archive.infolist():
        if not info.is_dir() and info.filename.endswith(".txt"):
            groups[Path(info.filename).name].append(info)
    chosen = []
    mirrors = 0
    for name in sorted(groups):
        members = sorted(groups[name], key=lambda x: x.filename)
        first = members[0]
        if any((x.CRC, x.file_size) != (first.CRC, first.file_size) for x in members):
            raise ValueError(f"Conflicting mirrored symbol: {name}")
        # CRC is an initial check; verify the actual bytes for mirrored datasets.
        if len(members) > 1:
            hashes = {hashlib.sha256(archive.read(x)).hexdigest() for x in members}
            if len(hashes) != 1:
                raise ValueError(f"Conflicting mirror hash: {name}")
        chosen.append(first)
        mirrors += len(members) - 1
    return chosen, mirrors


def read_daily(archive, member):
    with archive.open(member) as stream:
        frame = pd.read_csv(stream)
    if list(frame.columns) != ["Date", "Open", "High", "Low", "Close", "Volume", "OpenInt"]:
        raise ValueError("Unrecognized daily format")
    if not frame.Date.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Non-daily timestamp in daily loader")
    frame.index = pd.to_datetime(frame.pop("Date"), utc=True)
    frame.columns = [x.lower() for x in frame.columns]
    return validate_bars(frame)


def audit_zip(path):
    records = []
    with zipfile.ZipFile(path) as archive:
        members, mirrors = canonical_members(archive)
        metadata = [
            x.filename
            for x in archive.infolist()
            if any(token in x.filename.lower() for token in ("readme", "license", "metadata"))
        ]
        for member in members:
            content = archive.read(member)
            row = {
                "symbol": Path(member.filename).stem,
                "member": member.filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
            try:
                raw = pd.read_csv(io.BytesIO(content))
                row.update(columns=list(raw.columns), observations=len(raw))
                if "Date" not in raw:
                    raise ValueError("Date column missing")
                row["daily_dates_only"] = bool(
                    raw.Date.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
                )
                row["duplicates"] = int(raw.Date.duplicated().sum())
                if raw.empty:
                    raise ValueError("Empty instrument")
                row.update(
                    start=str(raw.Date.iloc[0]),
                    end=str(raw.Date.iloc[-1]),
                    nonzero_openint=int(raw.OpenInt.ne(0).sum()),
                )
                frame = read_daily(archive, member)
                # Calendar gaps include exchange holidays and missing sessions, not proof of bad data.
                gaps = frame.index.to_series().diff().dt.days
                row.update(
                    status="VALID_DAILY",
                    max_calendar_gap_days=int(gaps.max()) if len(frame) > 1 else 0,
                    calendar_gaps_over_4_days=int(gaps.gt(4).sum()),
                    group="ETF" if "ETFs/" in member.filename else "Stock",
                )
            except (ValueError, KeyError, pd.errors.EmptyDataError) as exc:
                row.update(status="REJECTED", reason=str(exc))
            records.append(row)
        count = sum(not x.is_dir() for x in archive.infolist())
    valid = [x for x in records if x["status"] == "VALID_DAILY"]
    return {
        "file": Path(path).name,
        "bytes": Path(path).stat().st_size,
        "sha256": sha256(path),
        "archive_files": count,
        "unique_symbols": len(members),
        "mirrored_files": mirrors,
        "valid_symbols": len(valid),
        "rejected_symbols": len(records) - len(valid),
        "first_date": min(x["start"] for x in valid),
        "last_date": max(x["end"] for x in valid),
        "frequency": "daily"
        if all(x.get("daily_dates_only", False) for x in records if x.get("observations", 0))
        else "mixed/unknown",
        "timezone": "date labels only; UTC localization is storage, not exchange execution time",
        "provider": "not documented; format resembles Stooq/Kaggle stocks, attribution unverified",
        "adjustment": "unknown; cannot establish split/dividend or point-in-time adjustments",
        "license": "not provided",
        "metadata_members": metadata,
        "biases": [
            "unverified survivor/delisted coverage",
            "no corporate-action metadata",
            "incomplete histories",
            "no exchange calendar or sectors",
            "static hindsight universe",
        ],
        "instruments": records,
    }


def resample_minutes(raw):
    validate_bars(raw, minute=True)
    grid = raw.reindex(pd.date_range(raw.index[0], raw.index[-1], freq="min"))
    volume = grid.volume.rolling(60, min_periods=60).sum().shift(1)
    quote = grid.quote_volume.rolling(60, min_periods=60).sum().shift(1)
    close = grid.close.shift(1)
    sigma = np.log(grid.close / grid.close.shift()).rolling(60, min_periods=60).std().shift(1)
    bars = grid.resample("30min", closed="left", label="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        minute_count=("open", "count"),
    )
    bars["bar_complete"] = bars.minute_count.eq(30)
    bars["prior_close"] = close.reindex(bars.index)
    bars["sigma60"] = sigma.reindex(bars.index)
    vwap = quote / volume.where(volume.gt(0))
    bars["z60"] = ((close - vwap) / (sigma * close)).reindex(bars.index)
    # first()/last() skip NaNs; mask incomplete bars so missing first minutes never shift execution.
    bars.loc[~bars.bar_complete, [*OHLCV, "quote_volume"]] = np.nan
    return bars


def read_binance_zip(path, *, quarantine_off_minute=False):
    with zipfile.ZipFile(path) as archive:
        files = [x for x in archive.namelist() if x.endswith(".csv")]
        if len(files) != 1:
            raise ValueError("Expected one Binance CSV")
        with archive.open(files[0]) as stream:
            raw = pd.read_csv(stream, header=None)
    timestamps = pd.to_numeric(raw[0], errors="raise")
    unit = "us" if timestamps.iloc[0] >= 10**15 else "ms"
    frame = raw.iloc[:, [1, 2, 3, 4, 5, 7]].copy()
    frame.columns = [*OHLCV, "quote_volume"]
    frame.index = pd.to_datetime(timestamps, unit=unit, utc=True)
    off_minute = frame.index != frame.index.floor("min")
    if off_minute.any() and quarantine_off_minute:
        frame = frame.loc[~off_minute].copy()
    frame.attrs["quarantined_off_minute_rows"] = (
        int(off_minute.sum()) if quarantine_off_minute else 0
    )
    return validate_bars(frame, minute=True)


def load_panels(directories):
    parts, manifest = [], []
    for directory in directories:
        for path in sorted(Path(directory).glob("btc_decisions_*.parquet")):
            parts.append(pd.read_parquet(path))
            manifest.append(
                {"file": path.name, "sha256": sha256(path), "source_directory": str(directory)}
            )
    if not parts:
        raise ValueError("No persisted BTC panels")
    frame = pd.concat(parts).sort_index()
    frame.index = frame.index.as_unit("ns")
    # Existing pre/post-cut panels overlap in August. Only identical rows can be deduplicated.
    dup = frame.index.duplicated(keep=False)
    if dup.any():
        for _, rows in frame[dup].groupby(level=0):
            if not all(rows.iloc[0].equals(rows.iloc[j]) for j in range(1, len(rows))):
                raise ValueError("Conflicting panel overlap")
        frame = frame[~frame.index.duplicated()]
    if str(frame.index.tz) != "UTC" or not frame.index.is_monotonic_increasing:
        raise ValueError("Invalid panel clock")
    expected = pd.date_range(frame.index[0], frame.index[-1], freq="30min")
    if not frame.index.equals(expected):
        raise ValueError("Panel has missing timestamps; preserve them explicitly")
    return frame, manifest


def load_local_prices(root, start, stop, cache):
    """Read BTC only from hourly local Binance parquet, retaining gaps and hashes."""
    hours = pd.date_range(start.floor("h"), stop.ceil("h"), freq="h", inclusive="both")
    paths = [
        Path(root) / f"sampled_marketdata_binance_1m.{h:%Y%m%d-%H}.parquet.snappy" for h in hours
    ]

    def read(path):
        if not path.is_file():
            return None, {"file": path.name, "status": "MISSING"}
        digest = sha256(path)
        parquet = pq.ParquetFile(path)
        if "symbol" not in parquet.schema_arrow.names:
            if parquet.metadata.num_rows:
                raise ValueError(f"Missing symbol schema: {path.name}")
            return None, {"file": path.name, "sha256": digest, "status": "EMPTY"}
        raw = pq.read_table(
            path, columns=["timestamp", "open"], filters=[("symbol", "=", "BTCUSDT")]
        ).to_pandas()
        series = pd.Series(raw.open.to_numpy(float), index=pd.to_datetime(raw.timestamp, utc=True))
        if series.index.has_duplicates or not np.isfinite(series).all() or (series <= 0).any():
            raise ValueError(f"Invalid minute source: {path.name}")
        if (series.index != series.index.floor("min")).any():
            raise ValueError(f"Off-minute source: {path.name}")
        return series, {"file": path.name, "sha256": digest, "status": "READ", "rows": len(series)}

    cache = Path(cache)
    source_manifest = []
    parts = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, (series, entry) in enumerate(pool.map(read, paths)):
            source_manifest.append(entry)
            if series is not None:
                parts.append(series)
            if i % 5000 == 0:
                print(f"minute source {i}/{len(paths)}", flush=True)
    if not parts:
        raise ValueError("No BTC minute data")
    result = pd.concat(parts).sort_index()
    if result.index.has_duplicates:
        raise ValueError("Duplicate minute across source files")
    result = result.reindex(pd.date_range(start, stop, freq="min"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    result.rename("open").to_frame().to_parquet(cache)
    return result, source_manifest
