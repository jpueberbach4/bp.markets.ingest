#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        helper.py
 Author:      JP Ueberbach
 Created:     2026-01-02
 Description: Utility functions for parsing path-based OHLCV query URIs.

              This module provides helpers for interpreting a slash-delimited
              query DSL used to request OHLCV (Open, High, Low, Close, Volume)
              time-series data. Its primary purpose is to convert path-encoded
              query strings into structured dictionaries suitable for downstream
              query resolution, validation, and execution.

              Responsibilities:
              
              - Extract symbol/timeframe selections from path segments
              - Apply default and user-specified temporal filters (after/until)
              - Parse output format and platform-specific flags (e.g., MT4)
              - Normalize all extracted values into a consistent dictionary
                structure for use in SQL query generation or API responses

              The path-based DSL is intentionally aligned with the internal
              builder syntax to ensure full compatibility. Users familiar
              with the builder can use the same syntax in the API.

 Usage:
     Use `parse_uri(uri: str)` to convert a path-based OHLCV query string
     into structured query options.

 Requirements:
     - Python 3.8+

 License:
     MIT License
===============================================================================
"""

from typing import Dict, Any
from urllib.parse import unquote_plus

def parse_uri(uri: str) -> Dict[str, Any]:
    """Parse a path-based OHLCV query URI into structured query options.

    This function interprets a slash-delimited query DSL embedded in the
    request path. It extracts symbol and timeframe selections, temporal
    filters, output format, and platform-specific flags, and normalizes
    them into a dictionary suitable for downstream query resolution.

    Supported path segments include:
        - select/{symbol},{timeframe}[,...]
        - after/{timestamp}
        - until/{timestamp}
        - output/{format}/[MT4]

    Args:
        uri (str):
            Path-encoded query string (excluding the API prefix).

    Returns:
        Dict[str, Any]:
            A dictionary containing parsed query options with the following
            keys:

            - select_data (list[str]):
                Normalized symbol/timeframe selection strings.
            - after (str):
                Inclusive lower timestamp bound.
            - until (str):
                Exclusive upper timestamp bound.
            - output_type (str | None):
                Requested output format (e.g., "JSON", "CSV", "JSONP").
            - mt4 (bool | None):
                Flag indicating MT4-compatible output.
            - options (list):
                Reserved for future extensions.
    """
    # Split URI into non-empty path segments
    parts = [p for p in uri.split("/") if p]

    # Initialize default query options
    result = {
        "select_data": [],
        "after": "1970-01-01 00:00:00",
        "until": "3000-01-01 00:00:00",
        "output_type": None,
        "mt4": None,
        "options": [],
    }

    # Iterate over path segments sequentially
    it = iter(parts)
    for part in it:
        # Handle symbol/timeframe selections
        if part == "select":
            val = next(it, None)
            if val:
                unquoted_val = unquote_plus(val)

                # Normalize comma-separated symbol/timeframe pairs
                if "," in val:
                    symbol_part, tf_part = unquoted_val.split(",", 1)
                    formatted_selection = f"{symbol_part}/{tf_part}"
                    result["select_data"].append(formatted_selection)
                else:
                    result["select_data"].append(unquoted_val)

        # Handle lower time bound
        elif part == "after":
            quoted_val = next(it, None)
            result["after"] = unquote_plus(quoted_val) if quoted_val else None

        # Handle upper time bound
        elif part == "until":
            quoted_val = next(it, None)
            result["until"] = unquote_plus(quoted_val) if quoted_val else None

        # Handle output format and optional MT4 flag
        elif part == "output":
            quoted_val = next(it, None)
            result["output_type"] = unquote_plus(quoted_val) if quoted_val else None

            quoted_val = next(it, None)
            result["mt4"] = True if quoted_val else None

    return result
