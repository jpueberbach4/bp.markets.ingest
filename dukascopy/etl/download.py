#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        download.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Description: Conversion to OOP - Download Dukascopy minute-level delta JSON 
              candle (HST) data for all symbols listed in 'symbols.txt'. Supports 
              historical and current-day downloads with automatic folder structure 
              management.

 Usage:
     python3 download.py

 Requirements:
     - Python 3.8+
     - pandas
     - requests

 License:
     MIT License
===============================================================================
"""
import os
import time
import orjson
import requests
import numpy as np
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Tuple, Optional

from config.app_config import AppConfig, DownloadConfig
from exceptions import *

class DownloadEngine:
    """
    Encapsulates HTTP access, rate limiting, retry logic, and continuity-safe
    merging of Dukascopy JSON delta candle data.
    """

    last_request_time = 0

    def __init__(self, config: DownloadConfig):
        """
        Initialize the download engine.

        Args:
            config: Download-related configuration parameters.
        """
        self.config = config
        self.session = requests.Session()

    def get_url(self, symbol: str, dt: date) -> str:
        """
        Build the Dukascopy API URL for a given symbol and date.

        Uses the live endpoint for the current UTC date and the historical
        endpoint for all past dates.

        Args:
            symbol: Trading symbol (e.g. "EURUSD").
            dt: Date for which data is requested.

        Returns:
            Fully-qualified Dukascopy API URL.
        """
        today_dt = datetime.now(timezone.utc).date()

        if dt == today_dt:
            # Live endpoint (no date path)
            return f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID"

        # Historical endpoint
        return (
            f"https://jetta.dukascopy.com/v1/candles/minute/"
            f"{symbol}/BID/{dt.year}/{dt.month}/{dt.day}"
        )

    def fetch_data(self, url: str) -> str:
        """
        Fetch JSON candle data from Dukascopy with rate limiting and retries.

        Applies:
        - Requests-per-second throttling
        - Exponential backoff on retryable errors
        - Immediate failure on non-retryable errors

        Args:
            url: Fully-qualified request URL.

        Returns:
            Raw response body as a string.

        Raises:
            requests.exceptions.RequestException: If all retries fail.
        """
        for attempt in range(self.config.max_retries):
            try:
                # Enforce global rate limit
                min_interval = (
                    1.0 / self.config.rate_limit_rps
                    if self.config.rate_limit_rps > 0
                    else 0
                )
                elapsed = time.monotonic() - DownloadEngine.last_request_time
                sleep_needed = max(0, min_interval - elapsed)

                if sleep_needed > 0:
                    #ime.sleep(sleep_needed)
                    pass

                # Perform HTTP request
                response = self.session.get(
                    url,
                    headers={
                        "Accept-Encoding": "gzip, deflate",
                        "User-Agent": "dukascopy-downloader/1.1 (+https://github.com/jpueberbach4/bp.markets.ingest/blob/main/dukascopy/etl/download.py)",
                    },
                    timeout=self.config.timeout,
                )
                response.raise_for_status()

                # Update request timestamp after success
                DownloadEngine.last_request_time = time.monotonic()
                return response.text

            except requests.exceptions.RequestException as e:
                status_code = getattr(e.response, "status_code", 0)

                # Retry only on server errors or rate limiting
                if (
                    attempt < self.config.max_retries - 1
                    and (status_code >= 500 or status_code == 429 or status_code == 503)
                ):
                    wait_time = self.config.backoff_factor ** attempt
                    print(f"{url} received {status_code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                raise

        return ""

    def filter_backfilled_items(self, temp_path: Path, cache_path: Path) -> bool:
        """
        Merge newly downloaded data into an existing cache while ensuring
        strict forward-only time continuity.

        Uses vectorized NumPy operations to identify the first new candle
        after the cached cutoff timestamp.

        Args:
            temp_path: Path to newly downloaded temporary JSON file.
            cache_path: Path to existing cached JSON file.

        Returns:
            True if a merge occurred, False otherwise.
        """
        if not cache_path.exists():
            return False

        with open(temp_path, "r+b") as f_temp, open(cache_path, "rb") as f_cache:
            data_temp = orjson.loads(f_temp.read())
            data_cache = orjson.loads(f_cache.read())

            if not data_cache["times"]:
                return False

            # Compute last cached timestamp
            cut_off = (
                np.cumsum(
                    np.array(data_cache["times"], dtype=np.int64)
                    * data_cache["shift"]
                )
                + data_cache["timestamp"]
            )[-1]

            # Compute timestamps for new data
            times_temp = (
                np.cumsum(
                    np.array(data_temp["times"], dtype=np.int64)
                    * data_temp["shift"]
                )
                + data_temp["timestamp"]
            )

            # Find first index strictly after cutoff
            mask = times_temp > cut_off
            indices = np.where(mask)[0]
            idx = indices[0] if indices.size > 0 else None

            if idx is not None:
                # Append only forward-continuous data
                for col in ["times", "opens", "highs", "lows", "closes", "volumes"]:
                    data_cache[col].extend(data_temp[col][idx:])

            # Overwrite temp file with merged result
            f_temp.seek(0)
            f_temp.truncate(0)
            f_temp.write(orjson.dumps(data_cache))

        return True


class DownloadWorker:
    """
    Coordinates file path resolution, environment rollovers (live vs historical),
    and atomic persistence of downloaded data.
    """

    def __init__(self, app_config: AppConfig):
        """
        Initialize the download worker.

        Args:
            app_config: Global application configuration.
        """
        self.app_config = app_config
        self.config = app_config.download
        self.engine = DownloadEngine(self.config)

    def resolve_paths(self, symbol: str, dt: date) -> Tuple[Path, Path, Path, bool]:
        """
        Resolve target, historical, and live file paths for a symbol/date pair.

        Args:
            symbol: Trading symbol.
            dt: Date of requested data.

        Returns:
            A tuple containing:
            - Final target path
            - Historical archive path
            - Live staging path
            - Boolean indicating historical mode
        """
        today_dt = datetime.now(timezone.utc).date()
        is_historical = not (dt == today_dt)

        hist_path = Path(self.config.paths.historic) / dt.strftime(
            f"%Y/%m/{symbol}_%Y%m%d.json"
        )
        live_path = Path(self.config.paths.live) / dt.strftime(
            f"{symbol}_%Y%m%d.json"
        )

        final_target = hist_path if is_historical else live_path
        return final_target, hist_path, live_path, is_historical

    def run(self, symbol: str, dt: date) -> bool:
        """
        Execute the full download and merge pipeline for a symbol and date.

        Args:
            symbol: Trading symbol.
            dt: Date to download.

        Returns:
            True if successful, False otherwise.
        """
        try:
            target, hist_path, live_path, is_historical = self.resolve_paths(symbol, dt)
            url = self.engine.get_url(symbol, dt)

            # Download raw JSON content
            content = self.engine.fetch_data(url)

            # Ensure target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = target.with_suffix(".tmp")

            # Write downloaded content to temporary file
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Merge forward-only data if a cache exists
            filter_source = live_path if live_path.is_file() else hist_path
            self.engine.filter_backfilled_items(tmp_path, filter_source)

            # Atomically replace target file
            os.replace(tmp_path, target)

            # Cleanup live file when historical data is finalized
            if is_historical:
                live_path.unlink(missing_ok=True)

            return True

        except Exception as e:
            raise


def fork_download(args: tuple) -> bool:
    """
    Multiprocessing entry point for downloading a single symbol/date pair.

    Args:
        args: Tuple of (symbol, date, app_config).

    Returns:
        True if download completed successfully.
    """
    try:
        symbol, dt, app_config = args
        worker = DownloadWorker(app_config)
        return worker.run(symbol, dt)
    except Exception as e:
        # Raise
        raise ForkProcessError(f"Error on download fork for {symbol}") from e

