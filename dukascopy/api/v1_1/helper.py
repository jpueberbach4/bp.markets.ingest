"""
===============================================================================
helper.py

Author:      JP Ueberbach
Created:     2026-01-02

Core helper utilities for path-based OHLCV query parsing, resolution,
execution, and output formatting.

This module implements the backbone of a filesystem-backed OHLCV query
pipeline. It parses a slash-delimited query DSL embedded in request paths,
resolves symbol/timeframe selections against discovered datasets, executes
DuckDB queries with indicator-aware warmup handling, and formats results
for API delivery.

Primary capabilities:
    - Parse path-encoded OHLCV query URIs into structured option dictionaries.
    - Normalize and validate timestamp inputs.
    - Discover OHLCV datasets from the filesystem using builder configuration.
    - Resolve user selections into concrete DuckDB-backed views.
    - Dynamically inspect indicator plugins to determine warmup requirements.
    - Execute parameterized DuckDB SQL queries with filtering, ordering,
      pagination, and modifiers (e.g., skiplast).
    - Merge and sort multi-symbol, multi-timeframe query results.
    - Generate API responses in JSON, JSONP, or CSV (including MT4-compatible
      formats).

The module is designed to integrate tightly with the internal OHLCV builder
pipeline and DuckDB execution layer, ensuring consistent behavior between
path-based queries and programmatic query construction.

Functions:
    normalize_timestamp(ts: str) -> str
        Normalize timestamp strings for consistent parsing.

    parse_uri(uri: str) -> Dict[str, Any]
        Parse a path-based OHLCV query DSL into structured options.

    discover_all(options: Dict) -> List[Dataset]
        Discover all available OHLCV datasets from the filesystem.

    discover_options(options: Dict) -> Dict
        Resolve user-requested selections against discovered datasets.

    generate_output(options: Dict, columns: List[str], results: List[tuple])
        Format query results as JSON, JSONP, or CSV.

    execute_sql(options: Dict) -> pandas.DataFrame
        Execute indicator-aware DuckDB queries and return merged results.

Internal helpers:
    _get_warmup_rows(...)
        Determine indicator warmup requirements.
    _get_warmup_timestamp(...)
        Resolve warmup-adjusted query start times.

Constants:
    CSV_TIMESTAMP_FORMAT
    CSV_TIMESTAMP_FORMAT_MT4_DATE
    CSV_TIMESTAMP_FORMAT_MT4_TIME

Requirements:
    - Python 3.8+
    - DuckDB
    - Pandas
    - FastAPI

License:
    MIT License
===============================================================================
"""

import csv
import io
import os
import orjson
import mmap
import re
import numpy as np
import pandas as pd
import duckdb 

from datetime import datetime, timezone
from typing import Dict, Any, List
from urllib.parse import unquote_plus
from pathlib import Path
from fastapi.responses import PlainTextResponse, JSONResponse

# Import builder utilities for resolving file-backed OHLCV selections
from builder.config.app_config import load_app_config
from util.dataclass import *
from util.discovery import *
from util.resolver import *
from api.state import *

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
        output = io.StringIO()
        if results:
            dict_results = [dict(zip(columns, row)) for row in results]
            writer = csv.DictWriter(output, fieldnames=columns)
            if not options.get('mt4'):
                # No header if MT4 flag is set
                writer.writeheader()

            writer.writerows(dict_results)

        return PlainTextResponse(
            content=output.getvalue(),
            media_type="text/csv",
        )

    return None


def _get_warmup_timestamp(symbol: str, tf: str, after_str: str, warmup_rows: int) -> str:
    """Returns the timestamp required to satisfy indicator warmup periods.

    This function queries DuckDB for the timestamp that is `warmup_rows`
    records prior to the provided `after_str` timestamp. It is typically used
    to ensure sufficient historical data is available before computing
    indicators that require lookback windows.

    Args:
        symbol (str): Trading symbol used to identify the DuckDB view.
        tf (str): Timeframe identifier used to identify the DuckDB view.
        after_str (str): ISO-formatted timestamp string representing the
            starting point for the query.
        warmup_rows (int): Number of rows to step backwards from `after_str`
            to determine the warmup timestamp.

    Returns:
        str: ISO-formatted timestamp string representing the warmup start
            time. Falls back to `after_str` if no earlier timestamp is found
            or if an error occurs.
    """
    # If no warmup is required, return the original timestamp
    if warmup_rows <= 0:
        return after_str

    # Construct the DuckDB view name for the symbol and timeframe
    view_name = f"{symbol}_{tf}_VIEW"

    # Convert the provided timestamp to UTC milliseconds
    after_ms = int(
        datetime.fromisoformat(after_str.replace(' ', 'T'))
        .replace(tzinfo=timezone.utc)
        .timestamp() * 1000
    )

    # Query for the timestamp `warmup_rows` before the given time
    query = f"""
        SELECT strftime(epoch_ms(time_raw::BIGINT), '{CSV_TIMESTAMP_FORMAT}') AS time
        FROM "{view_name}"
        WHERE time_raw < {after_ms}
        ORDER BY time_raw DESC
        LIMIT 1 OFFSET {warmup_rows - 1}
    """

    try:
        # Execute the query against the cached DuckDB connection
        from api.state import cache
        res = cache.get_conn().execute(query).fetchone()

        # Update the timestamp if a result is found
        if res:
            after_str = res[0]
    except Exception:
        # Silently fall back to the original timestamp on any error
        pass

    return after_str



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

def execute_sql(options):
    """Executes parameterized SQL queries against DuckDB to retrieve market data.

    This function builds and executes one SQL SELECT statement per requested
    symbol/timeframe pair. It accounts for indicator warmup requirements by
    extending the query window, optionally excludes the most recent candle,
    and merges all results into a single, time-sorted DataFrame.

    Args:
        options (dict): Query configuration dictionary. Expected keys include:
            - select_data: List of selections in the form
              [symbol, timeframe, input_filepath, modifiers, indicators].
            - order: Optional; 'asc' or 'desc' ordering by time (default: 'asc').
            - limit: Optional; number of rows to return per selection (default: 1440).
            - offset: Optional; row offset (currently unused).
            - after: ISO timestamp string indicating the start time.
            - until: ISO timestamp string indicating the end time.

    Returns:
        pd.DataFrame: Concatenated DataFrame containing market data for all
        requested symbol/timeframe combinations, sorted by time.
    """
    # Containers for generated SQL statements and resulting DataFrames
    select_sql_array = []
    select_df = []

    # Extract common query options with defaults
    order = options.get('order', 'asc').lower()
    limit = options.get('limit', 1440)
    offset = options.get('offset', 0)
    after_str = options.get('after')
    until_str = options.get('until')

    # Build and execute a SELECT statement for each requested dataset
    for item in options['select_data']:
        symbol, timeframe, input_filepath, modifiers, indicators = item

        # Determine required warmup rows for indicators
        warmup_rows = _get_warmup_rows(symbol, timeframe, after_str, indicators)
        warmup_after_str = _get_warmup_timestamp(
            symbol, timeframe, after_str, warmup_rows
        )
        warmup_limit = limit + warmup_rows

        # Convert ISO timestamps to epoch milliseconds
        after_ms = int(
            datetime.fromisoformat(warmup_after_str.replace(' ', 'T'))
            .replace(tzinfo=timezone.utc)
            .timestamp() * 1000
        )
        until_ms = int(
            datetime.fromisoformat(until_str.replace(' ', 'T'))
            .replace(tzinfo=timezone.utc)
            .timestamp() * 1000
        )

        # Base WHERE clause filtering by raw millisecond timestamps
        where_clause = (
            f"WHERE time_raw >= {after_ms} "
            f"AND time_raw < {until_ms}"
        )

        # Resolve DuckDB view name for the symbol/timeframe
        view_name = f"{symbol}_{timeframe}_VIEW"

        # Optionally exclude the most recent candle
        if "skiplast" in modifiers:
            where_clause += (
                f" AND time_raw < "
                f"(SELECT MAX(time_raw) FROM \"{view_name}\")"
            )

        # Construct the final SQL query
        sql = f"""
            SELECT 
                '{symbol}'::VARCHAR AS symbol,
                '{timeframe}'::VARCHAR AS timeframe,
                CAST(strftime(epoch_ms(time_raw::BIGINT), '%Y') AS VARCHAR) AS year,
                strftime(epoch_ms(time_raw::BIGINT), '{CSV_TIMESTAMP_FORMAT}') AS time,
                open, high, low, close, volume
            FROM "{view_name}"
            {where_clause}
            ORDER BY time_raw {order} LIMIT {warmup_limit}
        """

        # Execute query and collect the resulting DataFrame
        select_df.append(cache.get_conn().sql(sql).df())

    # Concatenate all result sets into a single DataFrame
    df = pd.concat(select_df)

    # Apply final sorting order
    is_asc = options.get('order', 'desc').lower() == 'asc'
    df = df.sort_values(by='time', ascending=is_asc).reset_index(drop=True)

    return df



