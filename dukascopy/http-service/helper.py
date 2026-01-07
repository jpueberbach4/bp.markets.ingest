#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        helper.py
 Author:      JP Ueberbach
 Created:     2026-01-02
 Description: Core helper utilities for path-based OHLCV query processing.

              This module provides a collection of helper functions used
              throughout the OHLCV data API and builder pipeline. It is
              responsible for interpreting a slash-delimited query DSL,
              resolving filesystem-backed data selections, dynamically
              loading indicator plugins, generating output payloads, and
              constructing DuckDB-compatible SQL queries.

              Key responsibilities include:

              - Parsing path-encoded OHLCV query URIs into structured options
                (symbols, timeframes, temporal filters, output format flags)
              - Normalizing timestamps and query parameters
              - Discovering and resolving available OHLCV data sources from
                the filesystem using builder configuration
              - Dynamically loading indicator plugins that expose a
                ``calculate`` interface
              - Generating formatted output in JSON, JSONP, or CSV form,
                including MT4-compatible variants
              - Building DuckDB SQL queries for querying CSV-based OHLCV data,
                including filtering, ordering, pagination, and modifiers

              The path-based DSL is intentionally aligned with the internal
              builder syntax to ensure full compatibility. Users familiar
              with the builder can reuse the same syntax when accessing the
              API.

 Usage:
     - Use ``parse_uri(uri: str)`` to convert a path-based query string into
       structured query options.
     - Use ``discover_options(options)`` to resolve selections against
       filesystem-backed OHLCV data.
     - Use ``generate_sql(options)`` to construct a DuckDB SQL query.
     - Use ``generate_output(options, columns, results)`` to format query
       results for API responses.
     - Use ``load_indicator_plugins()`` to discover and register indicator
       extensions.

 Requirements:
     - Python 3.8+
     - DuckDB
     - FastAPI

 License:
     MIT License
===============================================================================
"""

import importlib.util
import csv
import io
import os
import orjson

from typing import Dict, Any, List
from urllib.parse import unquote_plus
from pathlib import Path
from fastapi.responses import PlainTextResponse, JSONResponse

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
CSV_TIMESTAMP_FORMAT_MT4_DATE = "%Y.%m.%d"
CSV_TIMESTAMP_FORMAT_MT4_TIME = "%H:%M:%S"

PLUGIN_DIR = Path(__file__).parent / "plugins"

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


def load_indicator_plugins():
    """Dynamically load indicator plugins from the plugin directory.

    This function scans the configured plugin directory for Python files,
    dynamically imports each valid module, and registers its ``calculate``
    function if present. Each plugin is keyed by its filename (without the
    ``.py`` extension).

    Returns:
        dict[str, callable]: A dictionary mapping plugin names to their
        corresponding ``calculate`` functions. If the plugin directory does
        not exist or no valid plugins are found, an empty dictionary is
        returned.

    """ 
    plugins = {}
    if not PLUGIN_DIR.exists():
        return plugins

    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py") and not file.startswith("__"):
            plugin_name = file[:-3]
            file_path = PLUGIN_DIR / file
            
            spec = importlib.util.spec_from_file_location(plugin_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "calculate"):
                plugins[plugin_name] = module.calculate

    return plugins


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
    # Import builder utilities for resolving file-backed OHLCV selections
    from builder.helper import resolve_selections, get_available_data_from_fs
    from builder.config.app_config import load_app_config

    try:
        # Load builder configuration
        config_file = 'config.user.yaml' if Path('config.user.yaml').exists() else 'config.yaml'
        config = load_app_config(config_file)

        # Discover available OHLCV data sources from the filesystem
        available_data = get_available_data_from_fs(config.builder)

        # Resolve requested selections against available data
        options["select_data"] = resolve_selections(
            options["select_data"], available_data, False
        )[0]

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
    """Generate a DuckDB SQL query for retrieving OHLCV data from CSV sources.

    This function constructs a SQL query based on parsed query options,
    including symbol/timeframe selections, temporal filters, modifiers,
    ordering, and pagination. Each selection is translated into an
    individual SELECT statement, which are then combined using
    `UNION ALL` and wrapped in a final ordered, paginated query.

    Args:
        options (dict):
            Parsed query options containing:
            
            - select_data (list[tuple]):
                Tuples of the form
                (symbol, timeframe, input_filepath, modifiers).
            - after (str, optional):
                Inclusive lower timestamp bound (ISO-8601–like).
            - until (str, optional):
                Exclusive upper timestamp bound.
            - order (str, optional):
                Sort order, either "asc" or "desc".
            - limit (int, optional):
                Maximum number of rows to return.
            - offset (int, optional):
                Row offset for pagination.

    Returns:
        str:
            A complete DuckDB-compatible SQL query string.
    """
    # Collect individual SELECT statements (one per symbol/timeframe/file)
    select_sql_array = []

    for item in options['select_data']:
        # Unpack select tuple and append global temporal filters
        symbol, timeframe, input_filepath, modifiers, after, until = (
            item + tuple([options.get('after'), options.get('until')])
        )

        # Security check
        if not Path(input_filepath).is_absolute():
            raise ValueError("Invalid file path")

        # Columns selected from each CSV file, including normalized metadata
        select_columns = f"""
            '{symbol}'::VARCHAR AS symbol,
            '{timeframe}'::VARCHAR AS timeframe,
            CAST(strftime(Time, '%Y') AS VARCHAR) AS year,
            strptime(CAST(Time AS VARCHAR), '{CSV_TIMESTAMP_FORMAT}') AS time,
            open,
            high,
            low,
            close,
            volume
        """

        # Base temporal filter applied to all selections
        where_clause = f"""
            WHERE time >= TIMESTAMP '{after}'
            AND time < TIMESTAMP '{until}'
        """

        # Optional modifier: exclude the most recent candle
        # Useful when the latest bar may still be forming
        if "skiplast" in modifiers:
            where_clause += (
                f" AND time < ("
                f"SELECT MAX(time) "
                f"FROM read_csv_auto('{input_filepath}')"
                f")"
            )

        # Construct SELECT statement for this specific CSV input
        select_sql = f"""
            SELECT
                {select_columns}
            FROM read_csv_auto('{input_filepath}')
            {where_clause}
        """

        select_sql_array.append(select_sql)

    # Columns selected from the UNIONed result set
    # (time is formatted back to string form for output)
    if options['mt4']:
        # Columns selected from each CSV file, normalized for MT4
        select_columns = f"""
            strftime(time, '{CSV_TIMESTAMP_FORMAT_MT4_DATE}') AS date,
            strftime(time, '{CSV_TIMESTAMP_FORMAT_MT4_TIME}') AS time,
            open,
            high,
            low,
            close,
            volume
        """
    else:
        select_columns = f"""
            symbol,
            timeframe,
            CAST(strftime(Time, '%Y') AS VARCHAR) AS year,
            strftime(time, '{CSV_TIMESTAMP_FORMAT}') AS time,
            open,
            high,
            low,
            close,
            volume
        """

    # Final ordering and pagination parameters with defaults
    order = options.get('order') if options.get('order') else "asc"
    limit = options.get('limit') if options.get('limit') else 100
    offset = options.get('offset') if options.get('offset') else 0

    # Combine all SELECTs, apply ordering and pagination
    if options['mt4']:
        select_sql = f"""
            SELECT {select_columns}
            FROM (
                {''.join(select_sql_array)}
            )
            ORDER BY date {order}, time {order} 
            LIMIT {limit} OFFSET {offset};
        """
    else:
        select_sql = f"""
            SELECT {select_columns}
            FROM (
                {' UNION ALL '.join(select_sql_array)}
            )
            ORDER BY time {order}, symbol ASC, timeframe ASC
            LIMIT {limit} OFFSET {offset};
        """

    return select_sql