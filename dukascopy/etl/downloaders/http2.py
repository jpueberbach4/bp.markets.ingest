#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        download.py
Author:      JP Ueberbach
Created:     2025-12-19
Updated:     2026-02-08

Purpose:
    HTTP/2-based download engine for Dukascopy minute-level delta JSON
    candle data (HST-compatible format).

    This module implements the low-level network and merge logic required
    to safely and efficiently ingest Dukascopy candle data while respecting
    their rate limits and data quirks.

Core Responsibilities:
    - Build correct Dukascopy candle API URLs
    - Download historical and live (current-day) candle data
    - Enforce rate limiting across requests
    - Retry with exponential backoff on transient failures
    - Merge incremental live data without duplicating candles
    - Preserve strict timestamp continuity using vectorized math

Design Notes:
    - Uses HTTP/2 multiplexing via httpx for efficiency
    - Forces a single persistent TCP connection to avoid throttling
    - Shares rate-limit state across instances using a class variable
    - Uses NumPy for fast, deterministic timestamp reconstruction
    - Never mutates cached data unless new candles are strictly newer

Non-Responsibilities (by design):
    - File path resolution
    - Scheduling or orchestration
    - Parallel execution
    - Symbol discovery
    - CLI entrypoints

This module is intended to be used by higher-level workers or factories.

Requirements:
    - Python 3.8+
    - httpx
    - numpy
    - orjson

License:
    MIT License
===============================================================================
"""

import time
import asyncio
import orjson
import httpx
import numpy as np

from datetime import date, datetime, timezone
from pathlib import Path

from config.app_config import DownloadConfig
from exceptions import ProcessingError


class DownloadEngineHTTP2:
    """
    HTTP/2-optimized download engine for Dukascopy candle data.

    This class owns:
        - HTTP client lifecycle
        - API URL construction
        - Global rate limiting
        - Retry and backoff behavior

    One instance can be reused across many downloads.
    """

    # Global request timestamp shared across ALL instances.
    # This enforces rate limits even if multiple workers exist.
    last_request_time = time.monotonic()

    def __init__(self, config: DownloadConfig):
        """
        Initialize the HTTP/2 download engine.

        Args:
            config: Download-specific configuration containing
                timeouts, retry limits, backoff factors, and rate limits.
        """
        self.config = config

        # Force a single TCP connection and reuse it indefinitely.
        # Dukascopy is extremely sensitive to connection churn.
        self.limits = httpx.Limits(
            max_connections=1,
            max_keepalive_connections=1,
            keepalive_expiry=60.0,
        )

        # Persistent HTTP/2 client
        self.client = httpx.AsyncClient(
            http2=True,
            limits=self.limits,
            timeout=config.timeout,
        )

    def get_url(self, symbol: str, dt: date) -> str:
        """
        Construct the Dukascopy candle API URL for a symbol and date.

        Dukascopy uses:
            - A live endpoint for the current UTC day
            - A dated endpoint for all historical data

        Args:
            symbol: Trading symbol (e.g. "EURUSD").
            dt: Date of the requested candles (UTC).

        Returns:
            Fully qualified Dukascopy API URL.
        """
        today_dt = datetime.now(timezone.utc).date()

        # Current-day candles come from the live endpoint
        if dt == today_dt:
            return f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID"

        # Historical candles embed year/month/day in the URL
        return (
            "https://jetta.dukascopy.com/v1/candles/minute/"
            f"{symbol}/BID/{dt.year}/{dt.month}/{dt.day}"
        )

    async def fetch_data(self, url: str) -> str:
        """
        Download raw JSON candle data from Dukascopy.

        Behavior:
            - Enforces a global request rate limit
            - Retries with exponential backoff
            - Treats Dukascopy's 400 burst errors as retryable
            - Raises only after retries are exhausted

        Args:
            url: Fully qualified Dukascopy API endpoint.

        Returns:
            Raw JSON response body as a string.

        Raises:
            httpx.HTTPError: If all retry attempts fail.
            ProcessingError: As a final safeguard if no exception was raised.
        """
        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                # -------------------------------
                # Global rate limiting
                # -------------------------------
                min_interval = (
                    1.0 / self.config.rate_limit_rps
                    if self.config.rate_limit_rps > 0
                    else 0
                )

                elapsed = time.monotonic() - DownloadEngineHTTP2.last_request_time
                sleep_needed = max(0.0, min_interval - elapsed)

                if sleep_needed > 0:
                    await asyncio.sleep(sleep_needed)

                # -------------------------------
                # Perform HTTP request
                # -------------------------------
                response = await self.client.get(
                    url,
                    headers={
                        "Accept-Encoding": "gzip, deflate",
                        "User-Agent": (
                            "dukascopy-downloader-h2/1.1 "
                            "(+https://github.com/jpueberbach4)"
                        ),
                    },
                )

                # Raise immediately for non-2xx responses
                response.raise_for_status()

                # Success: update global timestamp
                DownloadEngineHTTP2.last_request_time = time.monotonic()
                return response.text

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exception = e
                
                # Determine status code
                status_code = 0
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code

                # Retry only on transient or known Dukascopy failure modes
                should_retry = (
                    attempt < self.config.max_retries - 1
                    and (
                        status_code == 0 
                        or status_code in (400, 429, 503) 
                        or status_code >= 500
                    )
                )

                if should_retry:
                    wait_time = self.config.backoff_factor ** attempt
                    await asyncio.sleep(wait_time)
                    continue

                # Non-retryable or retries exhausted
                raise last_exception

        # Final safeguard
        if last_exception:
            raise last_exception
            
        raise ProcessingError(f"Failed to fetch {url} after {self.config.max_retries} attempts.")

