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

from pathlib import Path

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
CSV_TIMESTAMP_FORMAT_MT4_DATE = "%Y.%m.%d"
CSV_TIMESTAMP_FORMAT_MT4_TIME = "%H:%M:%S"


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
