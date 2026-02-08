#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        helper.py

Author:      JP Ueberbach
Created:     2026-01-02
Updated:     2026-01-23
             2026-02-08 Polars nativeness

Core helper utilities for path-based OHLCV query parsing, resolution,
and output formatting.

This module provides the shared execution and formatting layer used by
the OHLCV API routes. It is responsible for translating a slash-delimited,
path-encoded query DSL into structured query options, resolving symbol
and timeframe selections against filesystem-backed datasets, normalizing
timestamps, and serializing query results into API-ready response formats.

The helpers in this module intentionally do not perform data retrieval
themselves. Instead, they prepare and post-process inputs and outputs
around the cache-backed data access and indicator execution layers.

Primary responsibilities:
    - Parse and normalize path-encoded OHLCV query URIs.
    - Normalize and validate timestamp inputs.
    - Resolve user selections into concrete dataset definitions using
      filesystem-backed discovery and selection resolution.
    - Enrich query options with resolved symbol/timeframe selections.
    - Format query results into JSON, JSONP, CSV, or NDJSON outputs.
    - Apply MT4-compatible CSV formatting when requested.
    - Stream large result sets efficiently to minimize memory usage.

Design notes:
    - Query parsing and dataset resolution are decoupled from data access.
    - Indicator warmup and execution are handled by downstream layers.
    - Streaming responses (CSV, NDJSON) are used for large result sets to
      reduce memory pressure and latency.
    - Polars is used as the internal DataFrame engine for performance.

Public functions:
    normalize_timestamp(ts: str) -> str
        Normalize timestamp strings for consistent parsing.

    parse_uri(uri: str) -> Dict[str, Any]
        Parse a path-based OHLCV query DSL into structured options.

    discover_options(options: Dict[str, Any]) -> Dict[str, Any]
        Resolve user selections against discovered datasets.

    generate_output(
        df: polars.DataFrame,
        options: Dict[str, Any]
    ) -> dict | PlainTextResponse | StreamingResponse | None
        Format query results according to the requested output type.

Internal helpers:
    _format_json(...)
        Serialize DataFrame results into structured JSON subformats.

    _stream_json(...)
        Stream newline-delimited JSON (NDJSON).

    _stream_csv(...)
        Stream CSV output with optional MT4 compatibility.

    _get_ms(...)
        Convert timestamps to epoch milliseconds (UTC).

Requirements:
    - Python 3.8+
    - Polars
    - FastAPI
    - orjson

License:
    MIT License
===============================================================================
"""

import csv
import io
import orjson
import re
import polars as pl

from datetime import datetime, timezone
from typing import Dict, Any, List
from urllib.parse import unquote_plus
from pathlib import Path
from fastapi.responses import PlainTextResponse, StreamingResponse, ORJSONResponse

# Import builder and utility components used for dataset discovery and resolution
from builder.config.app_config import load_app_config
from util.dataclass import *
from util.discovery import *
from util.resolver import *

from util.cache import MarketDataCache

# Canonical timestamp format used for human-readable output
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def normalize_timestamp(ts: str) -> str:
    """Normalize user-supplied timestamp strings for consistent parsing.

    This helper performs light normalization to make timestamps compatible
    with downstream ISO parsing by replacing common separators.

    Args:
        ts (str): Timestamp string supplied via the request URI.

    Returns:
        str: Normalized timestamp string, or the original value if empty.
    """
    if not ts:
        return ts

    # Replace dots with dashes (e.g. 2025.12.22 -> 2025-12-22)
    # Replace commas with spaces (e.g. 2025.12.22,13:59 -> 2025-12-22 13:59)
    normalized = ts.replace(".", "-").replace(",", " ")
    return normalized


def parse_uri(uri: str) -> Dict[str, Any]:
    """Parse a path-based OHLCV query URI into structured query options.

    This function interprets the slash-delimited DSL embedded in request
    paths and extracts selection clauses, temporal filters, output format,
    and platform-specific flags into a normalized options dictionary.

    Args:
        uri (str): Raw request URI path (excluding the API prefix).

    Returns:
        Dict[str, Any]: Parsed and partially normalized query options.
    """
    # Split URI into non-empty path segments
    parts = [p for p in uri.split("/") if p]

    # Initialize default option values
    result = {
        "select_data": [],
        "after": "1970-01-01 00:00:00",
        "until": "3000-01-01 00:00:00",
        "output_type": None,
        "mt4": None
    }

    # Iterate through path segments sequentially
    it = iter(parts)
    for part in it:
        if part == "select":
            # Selection clause: symbol and timeframe definitions
            val = next(it, None)
            if val:
                unquoted_val = unquote_plus(val)

                # Split on commas, ignoring commas inside brackets
                parts_split = re.split(r',(?![^\[]*\])', unquoted_val)

                if len(parts_split) >= 2:
                    symbol_part = parts_split[0]
                    tf_part = ",".join(parts_split[1:])
                    formatted_selection = f"{symbol_part}/{tf_part}"
                    result["select_data"].append(formatted_selection)
                else:
                    result["select_data"].append(unquoted_val)

        elif part == "after":
            # Lower time bound
            quoted_val = next(it, None)
            result["after"] = normalize_timestamp(unquote_plus(quoted_val)) if quoted_val else None

        elif part == "until":
            # Upper time bound
            quoted_val = next(it, None)
            result["until"] = normalize_timestamp(unquote_plus(quoted_val)) if quoted_val else None

        elif part == "output":
            # Output format selector
            quoted_val = next(it, None)
            result["output_type"] = unquote_plus(quoted_val) if quoted_val else None

        elif part == "MT4":
            # MT4 compatibility flag
            result["mt4"] = True

        else:
            # Generic key/value option pairs
            val = next(it, None)
            if val:
                result[part] = unquote_plus(val)

    return result


def discover_options(options: Dict):
    """Resolve and enrich data selection options using discovered datasets.

    This function converts user-specified selection strings into concrete
    symbol/timeframe definitions by resolving them against the registry
    of filesystem-backed OHLCV datasets.

    Args:
        options (Dict): Parsed query options containing unresolved selections.

    Returns:
        Dict: Options dictionary with resolved selection metadata injected.
    """
    try:
        # Initialize cache and selection resolver
        cache = MarketDataCache()
        resolver = SelectionResolver(cache.registry.get_available_datasets())

        # Resolve select_data into concrete dataset definitions
        options["select_data"], _ = resolver.resolve(options["select_data"])
        return options
    except Exception as e:
        raise


def generate_output(df: pl.DataFrame, options: Dict):
    """Generate formatted API output from a Polars DataFrame.

    This function dispatches to the appropriate formatter or streaming
    implementation based on the requested output type.

    Args:
        df (pl.DataFrame): Result DataFrame containing OHLCV data.
        options (Dict): Query options including output type and formatting flags.

    Returns:
        Response | None: A FastAPI-compatible response object, or None if
        the output type is unsupported.
    """
    callback = options.get('callback')

    # Default JSON output
    if options.get("output_type") == "JSON" or options.get("output_type") is None:
        return _format_json(df, options)

    # JSONP output for browser-based consumption
    if options.get("output_type") == "JSONP":
        payload = _format_json(df, options)
        json_data = payload.body.decode("utf-8")
        return PlainTextResponse(
            content=f"{callback}({json_data});",
            media_type="text/javascript",
        )

    # CSV streaming output
    if options.get("output_type") == "CSV":
        return _stream_csv(df, options)

    return None


def _add_human_readable_time_column(df: pl.DataFrame):
    """Add human-readable time and year columns using native Polars operations.

    This helper converts the `time_ms` column to UTC datetimes and derives
    formatted string and year columns for output serialization.

    Args:
        df (pl.DataFrame): Input DataFrame containing a `time_ms` column.

    Returns:
        pl.DataFrame: DataFrame with additional `time` and `year` columns.
    """
    # Convert epoch milliseconds to UTC datetime
    df = df.with_columns([
        pl.from_epoch("time_ms", time_unit="ms")
        .dt.replace_time_zone("UTC")
        .alias("_dt_temp")
    ])

    # Extract year and formatted timestamp string
    df = df.with_columns([
        pl.col("_dt_temp").dt.year().alias("year"),
        pl.col("_dt_temp").dt.strftime(TIMESTAMP_FORMAT).alias("time")
    ])

    # Reorder columns so metadata fields appear first
    priority = ['symbol', 'timeframe', 'year', 'time', 'time_ms']
    all_cols = df.columns

    head = [c for c in priority if c in all_cols]
    tail = [c for c in all_cols if c not in priority and c != "_dt_temp"]

    return df.select(head + tail)


def _format_json(df: pl.DataFrame, options: Dict):
    """Format a Polars DataFrame into structured JSON subformats.

    Supported subformats include record-oriented JSON, columnar arrays,
    time-series optimized layouts, and streaming NDJSON.

    Args:
        df (pl.DataFrame): Result DataFrame.
        options (Dict): Query options including subformat selection.

    Returns:
        ORJSONResponse | StreamingResponse: Formatted API response.
    """
    num_symbols = len(options.get('select_data', []))
    subformat = options.get('subformat', 1)

    # Drop index artifacts if present
    df = df.drop(["index", "level_0"], strict=False)

    # Subformat 1: Record-oriented JSON (list of dictionaries)
    if subformat == 1:
        df = _add_human_readable_time_column(df)
        df = df.drop(["time_ms", "year"], strict=False)
        return ORJSONResponse(content={
            "status": "ok",
            "options": options,
            "result": df.to_dicts(),
        })

    # Subformat 2: Columnar JSON (columns + value matrix)
    elif subformat == 2:
        df = df.drop(["time", "time_original", "year"], strict=False).rename({"time_ms": "time"})
        return ORJSONResponse(content={
            "status": "ok",
            "options": options,
            "columns": df.columns,
            "values": df.to_numpy().tolist(),
        })

    # Subformat 3: Time-series optimized layout
    elif subformat == 3:
        if num_symbols == 1:
            df = df.drop(
                ["symbol", "timeframe", "time", "time_original", "year", "indicators"],
                strict=False
            )
        else:
            df = df.drop(
                ["time", "time_original", "year", "indicators"],
                strict=False
            )

        df = df.rename({"time_ms": "time"})

        return ORJSONResponse(content={
            "status": "ok",
            "options": options,
            "columns": df.columns,
            "result": df.to_dict(as_series=False)
        })

    # Subformat 4: Streaming NDJSON
    elif subformat == 4:
        df = _add_human_readable_time_column(df)
        return _stream_json(df, options)

    else:
        raise Exception("Unknown subformat, only subformat 1, 2, 3 and 4 are known.")


def _stream_json(df: pl.DataFrame, options: Dict):
    """Stream a Polars DataFrame as newline-delimited JSON (NDJSON).

    Args:
        df (pl.DataFrame): Result DataFrame to stream.
        options (Dict): Query options (unused, reserved for future use).

    Returns:
        StreamingResponse: NDJSON streaming response.
    """
    async def json_generator_fast(df_gen: pl.DataFrame):
        for record in df_gen.to_dicts():
            yield orjson.dumps(record) + b"\n"

    return StreamingResponse(
        json_generator_fast(df),
        media_type="application/x-ndjson"
    )


def _stream_csv(df: pl.DataFrame, options: Dict):
    """Stream a Polars DataFrame as a CSV response.

    Applies optional MT4-compatible formatting when requested.

    Args:
        df (pl.DataFrame): Result DataFrame.
        options (Dict): Query options including MT4 and filename flags.

    Returns:
        StreamingResponse | None: CSV streaming response or None if empty.
    """
    # Add human-readable time fields and drop internal columns
    df = _add_human_readable_time_column(df)
    df = df.drop(['index', 'indicators', 'time_ms', 'year'], strict=False)

    if options.get('mt4'):
        # Derive MT4-specific date and time columns
        df = df.with_columns([
            pl.col("time").str.slice(0, 10).str.replace_all("-", ".").alias("date"),
            pl.col("time").str.slice(11, 8).alias("time_only")
        ])

        # Reorder columns to MT4-required layout
        cols_to_drop = ['symbol', 'timeframe', 'time']
        remaining_cols = [
            c for c in df.columns
            if c not in cols_to_drop + ['date', 'time_only']
        ]
        df = df.select(['date', 'time_only'] + remaining_cols)
        df = df.rename({"time_only": "time"})

    if not df.is_empty():
        async def csv_generator_fast(df_csv: pl.DataFrame):
            # Emit CSV header unless MT4 mode suppresses it
            if not options.get('mt4'):
                yield ','.join(df_csv.columns) + '\n'

            # Emit row data
            for row in df_csv.iter_rows():
                yield ','.join(str(val) if val is not None else "" for val in row) + '\n'

        filename = options.get('filename', 'data.csv')
        return StreamingResponse(
            csv_generator_fast(df),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    return None


def _get_ms(val):
    """Convert a numeric or timestamp value to epoch milliseconds (UTC).

    Args:
        val (int | float | str): Epoch milliseconds, numeric timestamp,
            or ISO-like datetime string.

    Returns:
        int: Epoch time in milliseconds (UTC).
    """
    if isinstance(val, (int, float)):
        return int(val)

    if isinstance(val, str) and val.isdigit():
        return int(val)

    return int(
        datetime.fromisoformat(val.replace(' ', 'T'))
        .replace(tzinfo=timezone.utc)
        .timestamp() * 1000
    )
