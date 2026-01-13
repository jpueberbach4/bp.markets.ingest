#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
helper.py

Author:      JP Ueberbach
Created:     2026-01-02

Core helper utilities for path-based OHLCV query processing.

This module provides functions for parsing and interpreting a
slash-delimited OHLCV query DSL, resolving filesystem-backed data
selections, generating DuckDB-compatible SQL queries, dynamically
loading indicator plugins, and formatting query output.

Key responsibilities:
    - Parse path-encoded OHLCV query URIs into structured options.
    - Normalize timestamps and query parameters.
    - Discover and resolve available OHLCV data sources from the filesystem.
    - Dynamically load indicator plugins exposing a `calculate` interface.
    - Generate formatted output in JSON, JSONP, or CSV (including MT4 variants).
    - Construct DuckDB SQL queries with filtering, ordering, pagination, and modifiers.

This module is aligned with the internal builder syntax, ensuring
compatibility with the OHLCV builder pipeline.

Functions:
    normalize_timestamp(ts: str) -> str
    parse_uri(uri: str) -> Dict[str, Any]
    discover_options(options: Dict) -> Dict
    generate_output(options: Dict, columns: List, results: List)
    generate_sql(options) -> str

Constants:
    CSV_TIMESTAMP_FORMAT: str
    CSV_TIMESTAMP_FORMAT_MT4_DATE: str
    CSV_TIMESTAMP_FORMAT_MT4_TIME: str

Requirements:
    - Python 3.8+
    - DuckDB
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

from api.state11 import cache

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

def generate_sql(options):
    """
    Build a DuckDB-compatible SQL query to retrieve OHLCV data from CSV
    files or pre-created DuckDB views.

    The function supports multiple symbol/timeframe selections, optional
    time filtering, result modifiers, ordering, and pagination. Each
    (symbol, timeframe) selection is translated into an individual
    SELECT statement. These statements are combined using UNION ALL and
    wrapped by a final outer query that handles ordering, formatting,
    limits, and offsets.

    The query supports two modes:
    - CSV mode (default): reads directly from CSV files via read_csv_auto
    - Binary mode: queries from pre-loaded DuckDB views using millisecond
      timestamps

    Args:
        options (dict):
            Parsed query options with the following keys:

            - select_data (list[tuple]):
                Tuples of the form:
                (symbol, timeframe, input_filepath, modifiers)

            - after (str):
                Inclusive lower time bound (ISO-8601–like string).

            - until (str):
                Exclusive upper time bound.

            - order (str, optional):
                Sort order for results ("asc" or "desc"). Defaults to "asc".

            - limit (int, optional):
                Maximum number of rows to return. Defaults to 1440.

            - offset (int, optional):
                Row offset for pagination. Defaults to 0.

            - fmode (str, optional):
                If set to "binary", queries DuckDB views instead of CSV files.

            - mt4 (bool, optional):
                If True, formats output columns for MT4-compatible CSV export.

    Returns:
        str:
            A complete SQL query string ready for execution in DuckDB.
    """

    # Holds individual SELECT statements (one per symbol/timeframe)
    select_sql_array = []

    # Extract common query options with defaults
    order = options.get('order', 'asc').lower()
    limit = options.get('limit', 1440)
    offset = options.get('offset', 0)
    after_str = options.get('after')
    until_str = options.get('until')

    # Build a SELECT statement for each requested dataset
    for item in options['select_data']:
        symbol, timeframe, input_filepath, modifiers = item[:4]

        # View name used when operating in binary mode
        view_name = f"{symbol}_{timeframe}_VIEW"

        # Enforce absolute paths for safety and consistency
        if not Path(input_filepath).is_absolute():
            raise ValueError("Invalid file path")


        # CSV-mode timestamp filtering
        where_clause = (
            f"WHERE Time >= '{after_str}'::TIMESTAMP "
            f"AND Time < '{until_str}'::TIMESTAMP"
        )

        # Optionally exclude the most recent candle
        if "skiplast" in modifiers:
            where_clause += (
                f" AND Time < "
                f"(SELECT MAX(Time) FROM read_csv_auto('{input_filepath}'))"
            )

        # CSV-mode SELECT statement (reads directly from CSV)
        select_sql = f"""
            SELECT 
                '{symbol}'::VARCHAR AS symbol,
                '{timeframe}'::VARCHAR AS timeframe,
                (epoch(Time::TIMESTAMP) * 1000)::BIGINT AS sort_key,
                open, high, low, close, volume
            FROM read_csv_auto('{input_filepath}')
            {where_clause}
        """

        # Store the generated SELECT statement
        select_sql_array.append(select_sql)

    # Define outer SELECT columns depending on output format
    if options.get('mt4'):
        # MT4-compatible CSV formatting (date/time split)
        outer_cols = f"""
            strftime(epoch_ms(sort_key::BIGINT), '{CSV_TIMESTAMP_FORMAT_MT4_DATE}') AS date,
            strftime(epoch_ms(sort_key::BIGINT), '{CSV_TIMESTAMP_FORMAT_MT4_TIME}') AS time,
            open, high, low, close, volume
        """
    else:
        # Standard CSV output with symbol/timeframe metadata
        outer_cols = f"""
            symbol,
            timeframe,
            CAST(strftime(epoch_ms(sort_key::BIGINT), '%Y') AS VARCHAR) AS year,
            strftime(epoch_ms(sort_key::BIGINT), '{CSV_TIMESTAMP_FORMAT}') AS time,
            open, high, low, close, volume
        """

    # Combine all SELECTs, apply ordering and pagination
    final_sql = f"""
        SELECT {outer_cols}
        FROM (
            {' UNION ALL '.join(select_sql_array)}
        )
        ORDER BY sort_key {order}, symbol ASC
        LIMIT {limit} OFFSET {offset};
    """

    return final_sql



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

        # Clamp the start index to zero to avoid negative indexing
        if after_idx < 0:
            after_idx = 0

        # Retrieve the data slice from cache
        chunk_df = cache.get_chunk(symbol, timeframe, after_idx, until_idx)

        # Accumulate results for later concatenation
        select_df.append(chunk_df)

    # Concatenate all retrieved chunks into a single DataFrame
    df = pd.concat(select_df)
    return df