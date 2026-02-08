#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        download.py
Author:      JP Ueberbach
Created:     2025-12-19
Updated:     2026-02-08

Purpose:
    Download worker responsible for orchestrating Dukascopy candle downloads
    using a pluggable download engine (HTTP/2 or legacy requests).

    This module sits ABOVE the actual download engines and handles:
        - File path resolution (live vs historical)
        - Temporary file handling and atomic writes
        - Engine selection via DownloadFactory
        - Bridging async engines into synchronous execution
        - Forward-only data merging
        - Cleanup of obsolete live files

Design Notes:
    - Does NOT perform network I/O directly
    - Does NOT know about retry or rate limiting
    - Delegates all HTTP behavior to engine implementations
    - Guarantees atomic file writes using temp files + os.replace
    - Can be safely used in multiprocessing contexts

Important:
    This module intentionally avoids:
        - Symbol discovery
        - Scheduling
        - Parallel coordination (handled externally)
        - Business logic inside the worker

Typical Call Stack:
    fork_download()
        -> DownloadWorker.run()
            -> DownloadEngine.fetch_data()
            -> DownloadEngine.filter_backfilled_items()

Requirements:
    - Python 3.8+
    - orjson
    - numpy
    - requests / httpx (via engine)
    - asyncio (for HTTP/2 bridge)

License:
    MIT License
===============================================================================
"""

import os
import asyncio

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Tuple

from config.app_config import AppConfig
from exceptions import ForkProcessError
from downloaders.factory import DownloadFactory


class DownloadWorker:
    """
    High-level download orchestrator for a single symbol/date pair.

    Responsibilities:
        - Resolve filesystem paths
        - Invoke the correct download engine
        - Bridge async engines into sync execution
        - Merge new data safely
        - Persist results atomically

    This class is intentionally boring and explicit.
    """

    def __init__(self, app_config: AppConfig):
        """
        Initialize the download worker.

        Args:
            app_config: Global application configuration containing
                download settings and filesystem paths.
        """
        self.app_config = app_config
        self.config = app_config.download

        # Resolve the correct engine implementation via factory.
        # This allows switching between HTTP/2 and legacy requests
        # without changing worker logic.
        self.engine = DownloadFactory.get_engine(
            self.config,
            mode=self.config.mode,
        )

    def resolve_paths(self, symbol: str, dt: date) -> Tuple[Path, Path, Path, bool]:
        """
        Resolve all filesystem paths for a symbol/date download.

        This method decides whether the data is considered:
            - Live (current UTC date)
            - Historical (any past date)

        Args:
            symbol: Trading symbol (e.g. "EURUSD").
            dt: Date of the requested candles (UTC).

        Returns:
            A tuple containing:
                - final_target: Path where the merged file will live
                - hist_path: Historical archive path
                - live_path: Live staging path
                - is_historical: True if dt is NOT today
        """
        today_dt = datetime.now(timezone.utc).date()

        # Historical mode = anything not equal to "today"
        is_historical = dt != today_dt

        # Historical files are organized by year/month
        hist_path = (
            Path(self.config.paths.historic)
            / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")
        )

        # Live files always live in the live directory
        live_path = (
            Path(self.config.paths.live)
            / dt.strftime(f"{symbol}_%Y%m%d.json")
        )

        # Final write target depends on historical vs live mode
        final_target = hist_path if is_historical else live_path

        return final_target, hist_path, live_path, is_historical

    def run(self, symbol: str, dt: date) -> bool:
        """
        Execute the complete download + merge pipeline for one symbol/date.

        Steps (very explicit on purpose):
            1. Resolve output paths
            2. Build Dukascopy API URL
            3. Fetch raw JSON using the selected engine
            4. Write data to a temporary file
            5. Merge forward-only candles if cache exists
            6. Atomically replace the target file
            7. Cleanup obsolete live files

        Args:
            symbol: Trading symbol to download.
            dt: Date to download (UTC).

        Returns:
            True if the operation completed successfully.

        Raises:
            Exception: Any unhandled error bubbles up intentionally.
        """
        try:
            # Resolve filesystem paths
            target, hist_path, live_path, is_historical = self.resolve_paths(symbol, dt)

            # Build the Dukascopy API URL
            url = self.engine.get_url(symbol, dt)

            # ---------------------------------------------------------
            # Fetch data
            # ---------------------------------------------------------
            # Some engines are async (HTTP/2), others are sync (requests).
            # We bridge async engines explicitly using asyncio.run().
            is_async_engine = hasattr(self.engine.fetch_data, "__call__") and asyncio.iscoroutinefunction(self.engine.fetch_data)

            if is_async_engine:
                content = asyncio.run(self.engine.fetch_data(url))
            else:
                content = self.engine.fetch_data(url)

            # No content means no work
            if not content:
                return False

            # Ensure target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)

            # Always write to a temporary file first
            tmp_path = target.with_suffix(".tmp")

            # Write raw JSON payload
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # ---------------------------------------------------------
            # Merge with existing cache (forward-only)
            # ---------------------------------------------------------
            # Prefer live cache if it exists, otherwise fall back
            # to historical cache.
            filter_source = live_path if live_path.is_file() else hist_path
            self.engine.filter_backfilled_items(tmp_path, filter_source)

            # ---------------------------------------------------------
            # Atomic replace
            # ---------------------------------------------------------
            # os.replace() guarantees atomicity on POSIX systems.
            os.replace(tmp_path, target)

            # If we just finalized historical data, remove stale live file
            if is_historical:
                live_path.unlink(missing_ok=True)

            return True

        except Exception:
            # Let the caller decide how to handle failures.
            raise


def fork_download(args: tuple) -> bool:
    """
    Multiprocessing entry point for downloading a single symbol/date pair.

    This function exists specifically so it can be passed directly to
    multiprocessing.Pool or similar APIs.

    Args:
        args: Tuple containing:
            - symbol: Trading symbol
            - dt: Date to download
            - app_config: Global application configuration

    Returns:
        True if the download completed successfully.

    Raises:
        ForkProcessError: Wrapped exception for clearer multiprocessing errors.
    """
    try:
        symbol, dt, app_config = args
        worker = DownloadWorker(app_config)
        return worker.run(symbol, dt)
    except Exception as e:
        raise ForkProcessError(
            f"Error during download fork for symbol={symbol}, date={dt}"
        ) from e
