"""
===============================================================================
helper.py

Author:      JP Ueberbach
Created:     2026-01-02

Core helper utilities for path-based OHLCV query parsing, resolution,
execution, and output formatting.

This module implements the core execution pipeline for the OHLCV API.
It parses a slash-delimited query DSL embedded in request paths, resolves
symbol and timeframe selections against filesystem-backed datasets,
determines indicator warmup requirements, retrieves cached market data,
and serializes results for API delivery.

The helpers in this module are shared across API endpoints to ensure
consistent behavior between path-based HTTP queries and internal,
programmatic query execution. The module integrates tightly with the
dataset discovery layer, selection resolver, indicator plugin system,
and cache-backed execution engine.

Primary responsibilities:
    - Parse and normalize path-encoded OHLCV query URIs.
    - Normalize and validate timestamp inputs.
    - Discover available OHLCV datasets from the filesystem using builder
      configuration.
    - Resolve user selections into concrete dataset definitions.
    - Inspect indicator plugins to determine warmup row requirements.
    - Execute indicator-aware, cache-backed data retrieval with filtering,
      ordering, limits, and modifiers (e.g., skiplast).
    - Merge and sort multi-symbol, multi-timeframe query results.
    - Generate API responses in JSON, JSONP, or CSV formats, including
      MT4-compatible CSV output.

Design notes:
    - Query execution operates on pre-built, cached OHLCV data rather than
      issuing raw SQL at request time.
    - Indicator warmup rows are automatically included to ensure correct
      computation of rolling and window-based indicators.
    - CSV output is streamed to support large result sets with low memory
      overhead.
    - The module is optimized for read-heavy, low-latency API workloads.

Public functions:
    normalize_timestamp(ts: str) -> str
        Normalize timestamp strings for consistent parsing.

    parse_uri(uri: str) -> Dict[str, Any]
        Parse a path-based OHLCV query DSL into structured options.

    discover_all(options: Dict) -> List[Dataset]
        Discover all available OHLCV datasets from the filesystem.

    discover_options(options: Dict) -> Dict
        Resolve user-requested selections against discovered datasets.

    generate_output(
        df: pandas.DataFrame,
        options: Dict[str, Any]
    ) -> dict | PlainTextResponse | StreamingResponse | None
        Format query results as JSON, JSONP, or CSV.

    execute(options: Dict) -> pandas.DataFrame
        Execute indicator-aware queries against cached OHLCV data and return
        merged results.

Internal helpers:
    _stream_csv(...)
        Stream a DataFrame as CSV with optional MT4 formatting.

    _get_warmup_rows(...)
        Determine indicator warmup row requirements.

Constants:
    CSV_TIMESTAMP_FORMAT
    CSV_TIMESTAMP_FORMAT_MT4_DATE
    CSV_TIMESTAMP_FORMAT_MT4_TIME

Requirements:
    - Python 3.8+
    - Pandas
    - FastAPI
    - DuckDB (build-time / preprocessing only)

License:
    MIT License
===============================================================================
"""

import csv
import io
import orjson
import re
import pandas as pd

from datetime import datetime, timezone
from typing import Dict, Any, List
from urllib.parse import unquote_plus
from pathlib import Path
from fastapi.responses import PlainTextResponse, StreamingResponse

# Import builder utilities for resolving file-backed OHLCV selections
from builder.config.app_config import load_app_config
from util.dataclass import *
from util.discovery import *
from util.resolver import *

from api.v1_1.plugin import indicator_registry
#from util.helper import discover_all
from util.cache import cache

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
CSV_TIMESTAMP_FORMAT_MT4_DATE = "%Y.%m.%d"
CSV_TIMESTAMP_FORMAT_MT4_TIME = "%H:%M:%S"

available_datasets = []

def normalize_timestamp(ts: str) -> str:
    if not ts:
        return ts
    # Replace dots with dashes: 2025.12.22 -> 2025-12-22
    # Replace commas with spaces: 2025.12.22,13:59 -> 2025.12.22 13:59
    normalized = ts.replace(".", "-").replace(",", " ")
    return normalized

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
        "mt4": None
    }

    # Iterate over path segments sequentially
    it = iter(parts)
    for part in it:
        # Handle symbol/timeframe selections
        if part == "select":
            val = next(it, None)
            if val:
                unquoted_val = unquote_plus(val)

                parts = re.split(r',(?![^\[]*\])', unquoted_val)

                if len(parts) >= 2:
                    symbol_part = parts[0]
                    # Rejoin the rest in case there were other commas outside brackets
                    tf_part = ",".join(parts[1:]) 
                    
                    formatted_selection = f"{symbol_part}/{tf_part}"
                    result["select_data"].append(formatted_selection)
                else:
                    result["select_data"].append(unquoted_val)

        # Handle lower time bound
        elif part == "after":
            quoted_val = next(it, None)
            result["after"] = normalize_timestamp(unquote_plus(quoted_val)) if quoted_val else None

        # Handle upper time bound
        elif part == "until":
            quoted_val = next(it, None)
            result["until"] = normalize_timestamp(unquote_plus(quoted_val)) if quoted_val else None

        # Handle output format and optional MT4 flag
        elif part == "output":
            quoted_val = next(it, None)
            result["output_type"] = unquote_plus(quoted_val) if quoted_val else None

        elif part == "MT4":
            result["mt4"] = True

        else:
            # Assume all other statements to be name/value
            val = next(it, None)
            if val:
                result[part] = unquote_plus(val)

    return result

def discover_options(options: Dict):
    """Resolve and enrich data selection options using filesystem-backed sources.

    This function loads the application configuration, discovers available
    OHLCV data sources from the filesystem, and resolves the user-provided
    data selections against those available sources. The resolved selections
    are written back into the ``options`` dictionary.

    Args:
        options (dict): Options dictionary containing user-requested settings.
            Must include the key ``select_data``, which specifies the desired
            OHLCV data selections.

    Returns:
        dict: The updated options dictionary with ``select_data`` replaced
        by the resolved and validated selections.

    Raises:
        Exception: Propagates any exception raised while loading configuration,
        discovering available data, or resolving selections.

    """

    try:
        # Resolve selections
        resolver = SelectionResolver(cache.registry.get_available_datasets())
        options["select_data"], _ = resolver.resolve(options["select_data"])
        return options
    except Exception as e:
        raise

def generate_output(df: pd.DataFrame, options: Dict):
    """Generates formatted output based on the requested output type.

    This function converts a pandas DataFrame into one of several supported
    output formats, including JSON, JSONP, and CSV. The output format is
    selected using the ``output_type`` value in the options dictionary.
    JSON output is used by default when no output type is specified.

    Args:
        df (pandas.DataFrame): DataFrame containing the result data to be
            serialized into the requested output format.
        options (Dict[str, Any]): Output configuration options. Supported
            keys include:
            - output_type (str, optional): One of "JSON", "JSONP", or "CSV".
              Defaults to "JSON" if not provided.
            - callback (str, optional): JavaScript callback function name
              used when output_type is "JSONP".

    Returns:
        dict | PlainTextResponse | StreamingResponse | None:
            - A dictionary for JSON output.
            - A PlainTextResponse containing JavaScript for JSONP output.
            - A StreamingResponse containing CSV data.
            - None if the requested output type is unsupported.
    """
    # Extract optional JSONP callback function name
    callback = options.get('callback')

    # Default JSON output
    if options.get("output_type") == "JSON" or options.get("output_type") is None:
        # Normalize DataFrame into row-oriented dictionaries
        return _format_json(df, options)

    # JSONP output for browser-based or cross-domain consumption
    if options.get("output_type") == "JSONP":
        # Normalize DataFrame into row-oriented dictionaries
        payload = _format_json(df, options)
        # Serialize payload and wrap in callback invocation
        json_data = orjson.dumps(payload).decode("utf-8")
        return PlainTextResponse(
            content=f"{callback}({json_data});",
            media_type="text/javascript",
        )

    # CSV output for file-based or analytical workflows
    if options.get("output_type") == "CSV":
        return _stream_csv(df, options)

    # Unsupported output type
    return None

def _format_json(df, options):
    """Format a DataFrame into structured JSON output.

    This function serializes a pandas DataFrame into one of several JSON
    subformats, controlled by the ``subformat`` option. Each subformat is
    designed for a different consumption pattern, ranging from simple
    record-oriented JSON to columnar or time-series–optimized layouts.

    Supported subformats:
        1. Record-oriented JSON (default)
        2. Column/value arrays (columnar JSON)
        3. Time-series–optimized structure with explicit OHLCV arrays

    Args:
        df (pandas.DataFrame): DataFrame containing OHLCV data and optional
            indicator columns.
        options (dict): Output options dictionary. Recognized keys:
            - subformat (int, optional): JSON subformat selector.
              Defaults to 1 when not provided.

    Returns:
        dict: A JSON-serializable dictionary containing formatted result
        data and request options.

    Raises:
        Exception: If an unsupported subformat is specified.
    """
    num_symbols = len(options.get('select_data'))
    # Resolve requested JSON subformat (default to 1)
    subformat = options.get('subformat') if options.get('subformat') else 1

    # ------------------------------------------------------------------
    # Subformat 1: Record-oriented JSON (list of row dictionaries)
    # ------------------------------------------------------------------
    if subformat == 1:
        # Remove internal or non-public columns
        df.drop(columns=['sort_key', 'year'], inplace=True, errors='ignore')

        return {
            "status": "ok",
            "options": options,
            "result": df.to_dict(orient='records'),
        }

    # ------------------------------------------------------------------
    # Subformat 2: Columnar JSON (columns + 2D values array)
    # ------------------------------------------------------------------
    elif subformat == 2:
        # Drop original timestamp columns and normalize sort_key -> time
        df = (
            df.drop(columns=['time', 'time_original', 'year'], errors='ignore')
            .rename(columns={'sort_key': 'time'})
        )       

        return {
            "status": "ok",
            "options": options,
            "columns": df.columns.tolist(),
            "values": df.values.tolist(),
        }

    # ------------------------------------------------------------------
    # Subformat 3: Time-series–optimized OHLCV structure
    # ------------------------------------------------------------------
    elif subformat == 3:
        # Drop non-essential metadata and normalize sort_key -> time
        if num_symbols == 1:
            df = (
                df.drop(
                    columns=['symbol', 'timeframe', 'time', 'time_original', 'year', 'indicators'],
                    errors='ignore'
                )
                .rename(columns={'sort_key': 'time'})
            )
        else:
            df = (
                df.drop(
                    columns=['time', 'time_original', 'year','indicators'],
                    errors='ignore'
                )
                .rename(columns={'sort_key': 'time'})
            )
        
        result = df.astype(object).where(df.notnull(), None).to_dict(orient='list')

        return {
            "status": "ok",
            "options": options,
            "columns": df.columns.tolist(),
            "result": result
        }
    # ------------------------------------------------------------------
    # Subformat 4: Stream–optimized OHLCV structure (NDJSON)
    # ------------------------------------------------------------------
    elif subformat == 4:
        return _stream_json(df, options)

    # ------------------------------------------------------------------
    # Unsupported subformat
    # ------------------------------------------------------------------
    else:
        raise Exception("Unknown subformat, only subformat 1, 2 and 3 is known.")


def _stream_json(df, options):
    """Stream a pandas DataFrame as newline-delimited JSON (NDJSON).

    This function converts each row of a DataFrame into an individual JSON
    object and streams the result incrementally using the NDJSON format
    (one JSON object per line). This approach is memory-efficient and well
    suited for large result sets and streaming consumers.

    Args:
        df (pandas.DataFrame): DataFrame containing the data to be streamed.
            Each row is serialized as an independent JSON object.
        options (dict): Output options dictionary. Currently unused, but
            included for interface consistency and future extensibility.

    Returns:
        StreamingResponse: A FastAPI StreamingResponse that emits NDJSON
        (`application/x-ndjson`) content.
    """
    async def json_generator_fast(df):
        # Convert the DataFrame to a list of row dictionaries and stream
        # each record as a standalone JSON object followed by a newline
        for record in df.to_dict(orient='records'):
            yield orjson.dumps(record) + b"\n"

    # Return a streaming NDJSON response suitable for large datasets
    return StreamingResponse(
        json_generator_fast(df),
        media_type="application/x-ndjson"
    )

def _stream_csv(df, options):
    """Streams a pandas DataFrame as a CSV HTTP response.

    This function prepares a DataFrame for CSV export, optionally applying
    MT4-compatible formatting rules, and returns a streaming response to
    efficiently handle large datasets. The CSV is generated incrementally
    to avoid loading the entire output into memory.

    Args:
        df (pandas.DataFrame): DataFrame containing the data to be exported.
            May include an ``indicators`` column with nested indicator data.
        options (Dict[str, Any]): Output configuration options. Supported
            keys include:
            - mt4 (bool, optional): If True, applies MT4-compatible column
              formatting and suppresses the CSV header.
            - filename (str, optional): Filename to use in the
              Content-Disposition response header.

    Returns:
        StreamingResponse | None: A streaming CSV HTTP response if data
        is present; otherwise, None.
    """
    # Remove the temporary columns
    df.drop(columns=['indicators','sort_key','year'], inplace=True, errors='ignore')

    # Apply MT4-specific column transformations if requested
    if options.get('mt4'):
        # Split the combined datetime column into date and time components
        temp_time = df['time'].astype(str).str.split(' ', expand=True)

        # Drop columns not required for MT4 output
        cols_to_drop = ['symbol', 'timeframe', 'sort_key', 'time', 'year', 'indicators']
        df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

        # Insert formatted date (YYYY.MM.DD) and time (HH:MM:SS) columns
        df.insert(0, 'date', temp_time[0].str.replace('-', '.'))
        df.insert(1, 'time', temp_time[1])

    # Extract column names and row values for CSV serialization
    columns = df.columns.tolist()
    results = df.values.tolist()

    # Only generate a CSV response if there is data to export
    if results:
        async def csv_generator_fast():
            # Emit the CSV header unless MT4-compatible output is requested
            if not options.get('mt4'):
                yield ','.join(columns) + '\n'

            # Stream each row incrementally to minimize memory usage
            for row in results:
                formatted = []
                for val in row:
                    formatted.append(str(val))
                yield ','.join(formatted) + '\n'

        # Filename handling
        filename = options.get('filename') if options.get('filename') else 'data.csv'

        # Return a streaming CSV response suitable for large exports
        return StreamingResponse(
            csv_generator_fast(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

def _get_ms(val):
    """Convert a numeric or timestamp value to epoch milliseconds (UTC).

    This helper function normalizes different timestamp representations
    into a single integer value expressed as milliseconds since the Unix
    epoch (UTC). It supports numeric inputs, digit-only strings, and
    ISO-formatted datetime strings.

    Args:
        val (int | float | str):
            The value to convert. Supported forms include:
            - int or float: Assumed to already represent milliseconds.
            - str of digits: Parsed directly as milliseconds.
            - ISO-formatted datetime string (e.g. "2025-01-12 13:59:00").

    Returns:
        int: The corresponding timestamp in epoch milliseconds (UTC).

    Raises:
        ValueError: If the input string cannot be parsed as an ISO datetime.
        TypeError: If the input type is unsupported.
    """
    # Fast path for numeric inputs already representing milliseconds
    if isinstance(val, (int, float)):
        return int(val)

    # Handle digit-only strings representing milliseconds
    if isinstance(val, str) and val.isdigit():
        return int(val)

    # Parse ISO-formatted datetime strings and convert to epoch milliseconds
    return int(
        datetime.fromisoformat(val.replace(' ', 'T'))
        .replace(tzinfo=timezone.utc)
        .timestamp() * 1000
    )



