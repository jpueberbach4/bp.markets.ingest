#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        download.py
Author:      JP Ueberbach
Created:     2025-12-19
Updated:     2026-02-08

Purpose:
    Legacy requests-based download engine for Dukascopy minute-level
    delta JSON candle data (HST-compatible format).

    This module provides a synchronous HTTP implementation of the
    Dukascopy downloader and exists primarily for:
        - Backward compatibility
        - Debugging and comparison against HTTP/2 behavior
        - Environments where async / httpx is not desired

Core Responsibilities:
    - Build correct Dukascopy candle API URLs
    - Download historical and live (current-day) candle data
    - Enforce global request rate limiting
    - Retry failed requests with exponential backoff
    - Merge incremental candle data without duplication
    - Preserve strict forward-only timestamp continuity

Design Notes:
    - Uses a persistent requests.Session for connection reuse
    - Shares rate-limit state across instances via a class variable
    - Uses NumPy vectorization for deterministic timestamp reconstruction
    - Intentionally mirrors the logic of the HTTP/2 engine where possible

Non-Responsibilities (by design):
    - File path resolution
    - Parallel execution
    - Scheduling or orchestration
    - Symbol discovery
    - CLI entrypoints

This module is typically instantiated via a factory and used by
higher-level workers.

Requirements:
    - Python 3.8+
    - requests
    - numpy
    - orjson

License:
    MIT License
===============================================================================
"""

import time
import orjson
import requests
import numpy as np

from datetime import date, datetime, timezone
from pathlib import Path

from config.app_config import DownloadConfig


class DownloadEngineRequests:
    """
    Synchronous, requests-based download engine for Dukascopy candle data.

    This class owns:
        - HTTP session lifecycle
        - URL construction
        - Global rate limiting
        - Retry and backoff behavior
        - Continuity-safe candle merging

    It is functionally equivalent to the HTTP/2 engine, but slower.
    """

    # Global timestamp shared across ALL instances.
    # This prevents exceeding Dukascopy rate limits even with multiple workers.
    last_request_time = time.monotonic()

    def __init__(self, config: DownloadConfig):
        """
        Initialize the download engine.

        Args:
            config: Download-specific configuration containing
                timeouts, retry limits, backoff factors, and rate limits.
        """
        self.config = config

        # Persistent session to reuse TCP connections
        self.session = requests.Session()

    def get_url(self, symbol: str, dt: date) -> str:
        """
        Construct the Dukascopy candle API URL for a symbol and date.

        Dukascopy uses:
            - A live endpoint for the current UTC date
            - A dated endpoint for all historical data

        Args:
            symbol: Trading symbol (e.g. "EURUSD").
            dt: Date of the requested candles (UTC).

        Returns:
            Fully qualified Dukascopy API URL.
        """
        today_dt = datetime.now(timezone.utc).date()

        # Current-day candles use the live endpoint
        if dt == today_dt:
            return f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID"

        # Historical candles embed year/month/day in the URL
        return (
            "https://jetta.dukascopy.com/v1/candles/minute/"
            f"{symbol}/BID/{dt.year}/{dt.month}/{dt.day}"
        )

    def fetch_data(self, url: str) -> str:
        """
        Download raw JSON candle data from Dukascopy.

        Behavior:
            - Enforces a global requests-per-second limit
            - Retries retryable failures with exponential backoff
            - Treats Dukascopy 400/429/5xx responses as transient
            - Raises immediately on non-retryable errors

        Args:
            url: Fully qualified Dukascopy API endpoint.

        Returns:
            Raw JSON response body as a string.

        Raises:
            requests.exceptions.RequestException: If retries are exhausted.
        """
        for attempt in range(self.config.max_retries):
            try:
                # --------------------------------
                # Global rate limiting
                # --------------------------------
                min_interval = (
                    1.0 / self.config.rate_limit_rps
                    if self.config.rate_limit_rps > 0
                    else 0
                )

                elapsed = time.monotonic() - DownloadEngineRequests.last_request_time
                sleep_needed = max(0.0, min_interval - elapsed)

                if sleep_needed > 0:
                    time.sleep(sleep_needed)

                # --------------------------------
                # Perform HTTP request
                # --------------------------------
                response = self.session.get(
                    url,
                    headers={
                        "Accept-Encoding": "gzip, deflate",
                        "User-Agent": (
                            "dukascopy-downloader-requests/1.1 "
                            "(+https://github.com/jpueberbach4)"
                        ),
                    },
                    timeout=self.config.timeout,
                )

                # Raise immediately for non-2xx responses
                response.raise_for_status()

                # Success: update global request timestamp
                DownloadEngineRequests.last_request_time = time.monotonic()
                return response.text

            except requests.exceptions.RequestException as e:
                status_code = getattr(e.response, "status_code", 0)

                # Retry only on transient or known Dukascopy failure modes
                if (
                    attempt < self.config.max_retries - 1
                    and status_code in (400, 429, 503)
                    or status_code >= 500
                ):
                    wait_time = self.config.backoff_factor ** attempt
                    time.sleep(wait_time)
                    continue

                # Non-retryable or retries exhausted
                raise

        # Defensive fallback (should never be reached)
        return ""

    def filter_backfilled_items(self, temp_path: Path, cache_path: Path) -> bool:
        """
        Merge forward-only candle data into an existing cache file.

        This guarantees:
            - No duplicate candles
            - No backward timestamps
            - Strict monotonic time ordering

        Timestamp continuity is reconstructed from Dukascopy's
        delta-encoded format using vectorized NumPy operations.

        Args:
            temp_path: Path to newly downloaded temporary JSON file.
            cache_path: Path to existing cached JSON file.

        Returns:
            True if a merge occurred, False otherwise.
        """
        # No cache means nothing to merge against
        if not cache_path.exists():
            return False

        # Open both files in binary mode for orjson
        with open(temp_path, "r+b") as f_temp, open(cache_path, "rb") as f_cache:
            data_temp = orjson.loads(f_temp.read())
            data_cache = orjson.loads(f_cache.read())

            # Empty cache = nothing meaningful to merge
            if not data_cache["times"]:
                return False

            # ------------------------------------
            # Compute last timestamp in cache
            # ------------------------------------
            cut_off = (
                np.cumsum(
                    np.array(data_cache["times"], dtype=np.int64)
                    * data_cache["shift"]
                )
                + data_cache["timestamp"]
            )[-1]

            # ------------------------------------
            # Compute timestamps for new data
            # ------------------------------------
            times_temp = (
                np.cumsum(
                    np.array(data_temp["times"], dtype=np.int64)
                    * data_temp["shift"]
                )
                + data_temp["timestamp"]
            )

            # Keep only candles strictly AFTER the cutoff
            mask = times_temp > cut_off
            indices = np.where(mask)[0]
            start_idx = indices[0] if indices.size > 0 else None

            if start_idx is not None:
                # Append only new candles (column-by-column on purpose)
                for col in (
                    "times",
                    "opens",
                    "highs",
                    "lows",
                    "closes",
                    "volumes",
                ):
                    data_cache[col].extend(data_temp[col][start_idx:])

            # Overwrite temp file with merged result
            f_temp.seek(0)
            f_temp.truncate(0)
            f_temp.write(orjson.dumps(data_cache))

        return True
