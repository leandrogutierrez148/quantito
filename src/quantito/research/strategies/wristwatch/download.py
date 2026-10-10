"""Optional public Binance archive acquisition; never called by tests or server."""

import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import certifi
import pandas as pd

from quantito.research.strategies.wristwatch.data import sha256
from quantito.research.strategies.wristwatch.report import write_json

BASE = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/"


def quarantine(path):
    """Keep a corrupt file for inspection without blocking subsequent retries."""
    path = Path(path)
    destination = path.with_name(path.name + ".corrupt")
    suffix = 1
    while destination.exists():
        destination = path.with_name(path.name + f".corrupt.{suffix}")
        suffix += 1
    path.rename(destination)
    return destination


def verified_archive(path, checksum, download_to):
    """Validate/commit independently of HTTP; download_to writes a .part path."""
    path = Path(path)
    if path.exists():
        if sha256(path) == checksum:
            return checksum
        quarantine(path)
    partial = path.with_name(path.name + ".part")
    try:
        download_to(partial)
        digest = sha256(partial)
        if digest != checksum:
            raise ValueError(f"Checksum mismatch {path.name}")
        # Same directory/filesystem: no final ZIP is visible before validation.
        partial.replace(path)
    except BaseException:
        # Preserve failed bytes, including interrupted downloads, for inspection.
        if partial.exists():
            quarantine(partial)
        raise
    return digest


def download_months(directory, first, last):
    out = Path(directory).expanduser().resolve()
    repo = Path(__file__).resolve().parents[5]
    if out == repo or repo in out.parents:
        raise ValueError("Market data must be outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    months = pd.date_range(first + "-01", last + "-01", freq="MS").strftime("%Y-%m")

    context = ssl.create_default_context(cafile=certifi.where())

    def request(url, timeout):
        for attempt in range(4):
            try:
                return urllib.request.urlopen(url, timeout=timeout, context=context)
            except urllib.error.HTTPError as exc:
                if exc.code == 404 or attempt == 3:
                    raise
            except (urllib.error.URLError, ConnectionError):
                if attempt == 3:
                    raise
            time.sleep(0.5 * (attempt + 1))
        raise RuntimeError("Request attempts exhausted")

    def fetch_once(month):
        filename = f"BTCUSDT-1m-{month}.zip"
        path = out / filename
        url = BASE + filename
        try:
            with request(url + ".CHECKSUM", 30) as response:
                checksum = response.read().decode().split()[0]

            def download_to(partial):
                with request(url, 60) as response, partial.open("wb") as stream:
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)

            digest = verified_archive(path, checksum, download_to)
            return {"file": filename, "url": url, "sha256": digest, "status": "VERIFIED"}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"file": filename, "url": url, "status": "UNAVAILABLE_404"}
            raise

    def fetch(month):
        for attempt in range(4):
            try:
                return fetch_once(month)
            except (urllib.error.URLError, ConnectionError):
                if attempt == 3:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError("Download attempts exhausted")

    with ThreadPoolExecutor(max_workers=2) as pool:
        manifest = list(pool.map(fetch, months))
    write_json(out / "download_manifest.json", manifest)
    return manifest
