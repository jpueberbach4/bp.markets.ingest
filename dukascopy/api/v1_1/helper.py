"""
===============================================================================
helper.py

Author:      JP Ueberbach
Created:     2026-01-02

Core helper utilities for path-based OHLCV query parsing, resolution,
execution, and output formatting.

This module implements the backbone of a filesystem-backed OHLCV query
pipeline. It parses a slash-delimited query DSL embedded in request paths,
resolves symbol/timeframe selections against discovered datasets, determines
indicator warmup requirements, executes cache-backed data retrieval, and
formats results for API delivery.

The module is designed to provide consistent behavior between path-based
API queries and programmatic query construction, integrating tightly with
the internal OHLCV builder pipeline, dataset discovery layer, indicator
plugin system, and execution cache.

Primary capabilities:
    - Parse path-encoded OHLCV query URIs into structured option dictionaries.
    - Normalize and validate timestamp inputs.
    - Discover OHLCV datasets from the filesystem using builder configuration.
    - Resolve user selections into concrete dataset definitions.
    - Dynamically inspect indicator plugins to determine warmup requirements.
    - Execute indicator-aware, cache-backed queries with filtering,
      ordering, limits, and modifiers (e.g., skiplast).
    - Merge and sort multi-symbol, multi-timeframe query results.
    - Generate API responses in JSON, JSONP, or CSV formats, including
      MT4-compatible CSV output.

Key design notes:
    - Query execution operates on pre-built, cached OHLCV data rather than
      issuing raw SQL at request time.
    - Indicator warmup rows are automatically included to ensure correct
      computation of rolling and window-based indicators.
    - The module is optimized for read-heavy, API-driven workloads.

Functions:
    normalize_timestamp(ts: str) -> str
        Normalize timestamp strings for consistent parsing.

    parse_uri(uri: str) -> Dict[str, Any]
        Parse a path-based OHLCV query DSL into structured options.

    discover_all(options: Dict) -> List[Dataset]
        Discover all available OHLCV datasets from the filesystem.

    discover_options(options: Dict) -> Dict
        Resolve user-requested selections against discovered datasets.

    generate_output(
        options: Dict,
        columns: List[str],
        results: List[tuple]
    ) -> dict | PlainTextResponse | None
        Format query results as JSON, JSONP, or CSV.

    execute(options: Dict) -> pandas.DataFrame
        Execute indicator-aware queries against cached OHLCV data and return
        merged results.

Internal helpers:
    _get_warmup_rows(...)
        Determine indicator warmup row requirements.

Constants:
    CSV_TIMESTAMP_FORMAT
    CSV_TIMESTAMP_FORMAT_MT4_DATE
    CSV_TIMESTAMP_FORMAT_MT4_TIME

Requirements:
    - Python 3.8+
    - Pandas
    - DuckDB (for build-time processing)
    - FastAPI

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
from api.state11 import *

from api.v1_1.plugin import indicator_registry

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
CSV_TIMESTAMP_FORMAT_MT4_DATE = "%Y.%m.%d"
CSV_TIMESTAMP_FORMAT_MT4_TIME = "%H:%M:%S"

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


def discover_all(options: Dict):
    """Discovers all datasets based on the application configuration.

    This function loads the application configuration from a user-specific
    YAML file if it exists, otherwise it falls back to the default config.
    It then initializes a `DataDiscovery` instance using the builder
    configuration and scans the filesystem for available datasets.

    Args:
        options (Dict): A dictionary of optional parameters (currently unused).

    Returns:
        List[Dataset]: A list of Dataset instances found in the filesystem.
    """
    # Determine which configuration file to load: user-specific or default
    config_file = 'config.user.yaml' if Path('config.user.yaml').exists() else 'config.yaml'

    # Load the application configuration from the YAML file
    config = load_app_config(config_file)

    # Initialize the DataDiscovery instance with the builder configuration
    discovery = DataDiscovery(config.builder)

    # Scan the filesystem and return the discovered datasets
    return discovery.scan()



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
        # Load builder configuration
        config_file = 'config.user.yaml' if Path('config.user.yaml').exists() else 'config.yaml'
        config = load_app_config(config_file)

        # Initialize discovery
        discovery = DataDiscovery(config.builder)
        available = discovery.scan()

        # Resolve selections
        resolver = SelectionResolver(available)
        options["select_data"], _ = resolver.resolve(options["select_data"])

        return options
    except Exception as e:
        raise

def generate_output(options: Dict, columns: List, results: List):
    """Generate formatted output based on the requested output type.

    This function supports JSON, JSONP, and CSV output formats. The output
    format is determined by the ``output_type`` value in the ``options``
    dictionary. JSON is used by default when no output type is specified.

    Args:
        options (dict): Configuration options controlling output behavior.
            Expected keys include:
                - output_type (str, optional): One of "JSON", "JSONP", or "CSV".
                  Defaults to "JSON" if not provided.
                - callback (str, optional): JavaScript callback function name
                  used when output_type is "JSONP".
                - mt4 (bool, optional): If True, suppresses CSV header output.
        columns (list[str]): Column names corresponding to each value in a
            result row.
        results (list[tuple]): Query result rows, where each tuple aligns
            positionally with ``columns``.

    Returns:
        dict | PlainTextResponse | None:  
        - A dictionary for JSON output.  
        - A PlainTextResponse containing JavaScript for JSONP output.  
        - A PlainTextResponse containing CSV data for CSV output.  
        - None if the requested output type is unsupported.

    """
    callback = options.get('callback')
    # Default JSON output
    if options.get("output_type") == "JSON" or options.get("output_type") is None:
        return {
            "status": "ok",
            "options": options,
            "result": [dict(zip(columns, row)) for row in results],
        }

    # JSONP output for browser-based consumption
    if options.get("output_type") == "JSONP":
        payload = {
            "status": "ok",
            "options": options,
            "result": [dict(zip(columns, row)) for row in results],
        }

        json_data = orjson.dumps(payload).decode("utf-8")
        return PlainTextResponse(
            content=f"{callback}({json_data});",
            media_type="text/javascript",
        )

    # CSV output for file-based or analytical workflows
    if options.get("output_type") == "CSV":
        return _csv_output(results,columns,options)

    return None

def _csv_output(results, columns, options):
    """Streams query results as a CSV response.

    This function formats result rows into CSV-compatible text and returns
    a streaming HTTP response to efficiently handle large datasets without
    loading the entire output into memory. Float values are formatted with
    fixed precision, and missing values are emitted as empty fields.

    Args:
        results (Iterable[Iterable[Any]]): Row-oriented result data to be
            serialized into CSV format.
        columns (List[str]): Column names to be used as the CSV header.
        options (Dict[str, Any]): Output configuration options. If the
            ``mt4`` flag is set, the CSV header row is omitted.

    Returns:
        StreamingResponse | None: A streaming CSV HTTP response if results
        are present; otherwise, None.
    """
    # Only generate a CSV response if there are results to output
    if results:
        async def csv_generator_fast():
            # Emit header row unless MT4-compatible output is requested
            if not options.get('mt4'):
                yield ','.join(columns) + '\n'

            # Stream each row incrementally to avoid high memory usage
            for row in results:
                formatted = []

                for val in row:

                    formatted.append(str(val))

                yield ','.join(formatted) + '\n'

        # Return a streaming CSV response suitable for large exports
        return StreamingResponse(
            csv_generator_fast(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={options.get('filename')}"
            }
        )




def _get_warmup_rows(symbol: str, timeframe: str, after_str: str, indicators: List[str]) -> int:
    """Determine the maximum warmup row count required by a set of indicators.

    This function inspects each requested indicator plugin to determine how many
    historical rows are required before the `after_str` timestamp in order to
    correctly compute indicator values (e.g., rolling windows). The maximum
    warmup requirement across all indicators is returned.

    Args:
        symbol (str): Trading symbol (e.g., "EURUSD"). Included for interface
            consistency and future extensibility.
        timeframe (str): Timeframe identifier (e.g., "5m", "1h"). Included for
            interface consistency and future extensibility.
        after_str (str): ISO-formatted timestamp string representing the starting
            point of the query. Not modified by this function.
        indicators (List[str]): List of indicator strings (e.g., ["sma_20", "bbands_20_2"]).

    Returns:
        int: The maximum number of warmup rows required across all indicators.
    """
    # Track the largest warmup requirement found
    max_rows = 0

    # Iterate through all requested indicators
    for ind_str in indicators:
        parts = ind_str.split('_')
        name = parts[0]

        # Skip indicators that are not registered
        if name not in indicator_registry:
            continue

        plugin_func = indicator_registry[name]

        # Initialize indicator options with raw positional parameters
        ind_opts = {"params": parts[1:]}

        # Map positional arguments if the plugin defines a mapper
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            ind_opts.update(plugin_func.__globals__["position_args"](parts[1:]))

        # Query the plugin for its warmup row requirement, if defined
        if hasattr(plugin_func, "__globals__") and "warmup_count" in plugin_func.__globals__:
            warmup_rows = plugin_func.__globals__["warmup_count"](ind_opts)
            max_rows = max(max_rows, warmup_rows)

    return max_rows

def execute(options):
    """Executes parameterized queries against cached market data and returns
    a combined DataFrame.

    For each requested (symbol, timeframe) pair, this function determines the
    required indicator warmup window, converts time boundaries to epoch
    milliseconds, computes record index ranges, retrieves the corresponding
    data chunks from cache, and concatenates all results into a single
    DataFrame.

    Args:
        options (dict): Query configuration dictionary with the following keys:
            select_data (list): List of selections in the form
                [symbol, timeframe, input_filepath, modifiers, indicators].
            order (str, optional): Sort order, either 'asc' or 'desc'.
                Defaults to 'asc'.
            limit (int, optional): Maximum number of rows to return per
                selection, excluding warmup rows. Defaults to 1440.
            offset (int, optional): Row offset (currently unused).
            after (str): ISO-format timestamp indicating the start time.
            until (str): ISO-format timestamp indicating the end time.

    Returns:
        pd.DataFrame: Concatenated DataFrame containing all retrieved market
        data, sorted by time.
    """
    # Containers for intermediate DataFrames
    select_df = []

    # Extract common query options with defaults
    order = options.get('order', 'asc').lower()
    limit = options.get('limit', 1440)
    offset = options.get('offset', 0)
    after_str = options.get('after')
    until_str = options.get('until')

    # Process each requested dataset
    for item in options['select_data']:
        symbol, timeframe, input_filepath, modifiers, indicators = item

        # Determine how many warmup rows are needed for indicators
        warmup_rows = _get_warmup_rows(symbol, timeframe, after_str, indicators)

        # Convert ISO timestamps to epoch milliseconds (UTC)
        after_ms = int(
            datetime.fromisoformat(after_str.replace(' ', 'T'))
            .replace(tzinfo=timezone.utc)
            .timestamp() * 1000
        )
        until_ms = int(
            datetime.fromisoformat(until_str.replace(' ', 'T'))
            .replace(tzinfo=timezone.utc)
            .timestamp() * 1000
        )

        # Total number of rows to retrieve, including warmup
        total_limit = limit + warmup_rows

        # Find index positions in cache for the requested time range
        after_idx = cache.find_record(symbol, timeframe, after_ms, "right")
        until_idx = cache.find_record(symbol, timeframe, until_ms, "right")

        # Extend the start index backward to include warmup rows
        after_idx = after_idx - warmup_rows

        # Enforce the total row limit depending on sort order
        if until_idx - after_idx > total_limit:
            if order == "desc":
                after_idx = until_idx - total_limit
            if order == "asc":
                until_idx = after_idx + total_limit

        max_idx = cache.get_record_count(symbol, timeframe)

        # Never slice beyond last row
        if until_idx > max_idx:
            until_idx = max_idx

        # Clamp the start index to zero to avoid negative indexing
        if after_idx < 0:
            after_idx = 0

        # Skiplast handling
        if until_idx == max_idx and "skiplast" in modifiers:
            until_idx -= 1



        # Retrieve the data slice from cache
        chunk_df = cache.get_chunk(symbol, timeframe, after_idx, until_idx)

        # Accumulate results for later concatenation
        select_df.append(chunk_df)

    # Concatenate all retrieved chunks into a single DataFrame
    df = pd.concat(select_df)
    return df




