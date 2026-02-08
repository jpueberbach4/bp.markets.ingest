#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        download.py
Author:      JP Ueberbach
Created:     2025-12-19
Updated:     2026-02-08

Purpose:
    Factory module for selecting and instantiating Dukascopy download engines.

    This file does NOT perform any downloading itself.

    Instead, it provides a single, centralized decision point for choosing
    which download engine implementation to use based on configuration or
    runtime preferences (e.g. HTTP/2 vs legacy requests).

Responsibilities:
    - Abstract engine selection behind a simple interface
    - Return fully initialized download engine instances
    - Provide a sensible default engine choice

Design Notes:
    - Keeps protocol-specific logic out of calling code
    - Makes it trivial to add new engines (e.g. aiohttp, curl bindings)
    - Prevents hard-coding engine classes throughout the codebase

Non-Responsibilities (by design):
    - Network I/O
    - Retry logic
    - Rate-limit handling
    - File persistence
    - Scheduling or orchestration

Usage Example:
    engine = DownloadFactory.get_engine(config)
    engine.download(symbol, date)

Requirements:
    - Python 3.8+
    - Project-specific download engine implementations

License:
    MIT License
===============================================================================
"""

from typing import Union

from config.app_config import DownloadConfig
from etl.downloaders.requests import DownloadEngineRequests
from etl.downloaders.http2 import DownloadEngineHTTP2


class DownloadFactory:
    """
    Factory for creating download engine instances.

    This class exists to:
        - Decouple engine selection from business logic
        - Centralize protocol decisions
        - Make engine swapping a one-line change

    All methods are static because:
        - No internal state is required
        - This class should never be instantiated
    """

    @staticmethod
    def get_engine(
        config: DownloadConfig,
        mode: str = "http2",
    ) -> Union[DownloadEngineRequests, DownloadEngineHTTP2]:
        """
        Return a download engine instance based on the requested mode.

        Args:
            config: Download configuration object containing timeouts,
                retry limits, paths, and other engine settings.
            mode: Download protocol to use.
                Supported values:
                    - "http2": HTTP/2 multiplexed engine (recommended)
                    - "requests": Legacy requests-based engine

        Returns:
            An initialized download engine instance matching the requested mode.

        Raises:
            ValueError: If an unsupported mode is provided.
        """
        # Normalize mode to lowercase so callers don't have to care
        mode = mode.lower()

        print(mode)

        # HTTP/2 engine:
        # - Uses a single persistent TCP connection
        # - Much faster for bulk ingestion
        # - Better behaved with Dukascopy rate limits
        if mode == "http2":
            return DownloadEngineHTTP2(config)

        # Legacy requests engine:
        # - Easier to debug
        # - Slower
        # - Kept for fallback and comparison purposes
        if mode == "requests":
            return DownloadEngineRequests(config)

        # If we reach this point, the caller passed nonsense
        raise ValueError(
            f"Unknown download mode: {mode}. "
            "Valid options are 'http2' or 'requests'."
        )

    @staticmethod
    def get_default_mode() -> str:
        """
        Return the recommended default download mode.

        This exists so the default can be changed in ONE place without
        hunting through the codebase.

        Returns:
            The default download mode string.
        """
        # HTTP/2 is the preferred and best-tested option
        return "http2"
