#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        routes.py
 Author:      JP Ueberbach
 Created:     2026-01-02
 Description: FastAPI router implementing a versioned OHLCV and indicator API.

              This module defines the public HTTP API for accessing OHLCV
              (Open, High, Low, Close, Volume) time-series data and derived
              indicators via a path-based query DSL. It exposes multiple
              versioned endpoints under the ``/ohlcv/{version}`` namespace.

              The API supports:

              - Executing raw OHLCV queries using a slash-delimited query DSL
              - Listing available symbols and timeframes discovered from the
                filesystem
              - Executing dynamically loaded indicator plugins against
                resolved OHLCV data
              - Pagination, ordering, and platform-specific options (e.g. MT4)
              - Multiple output formats including JSON, JSONP, and CSV

              Request processing generally follows this pipeline:

              - Parse the path-based DSL into structured query options
              - Validate pagination, ordering, and output constraints
              - Resolve requested symbol/timeframe selections against
                filesystem-backed OHLCV data using builder configuration
              - Translate resolved options into DuckDB-compatible SQL
              - Execute queries against CSV sources using an in-memory
                DuckDB instance
              - Optionally apply indicator functions to query results
              - Serialize results into the requested output format

              Indicator functionality is extensible via a plugin system.
              Indicator modules are dynamically loaded at startup and must
              expose a ``calculate(data, options)`` callable.

              The path-based DSL intentionally mirrors the syntax of the
              internal builder, ensuring full compatibility and making the
              API intuitive for users already familiar with the builder
              workflow.

 Usage:
     This module is included as part of the FastAPI application router
     configuration and should not be executed directly.

 TODO: Think of a way to better handle "warmup rows" for indicators

 Requirements:
     - Python 3.8+
     - FastAPI
     - DuckDB

 License:
     MIT License
===============================================================================
"""

import mmap
import time
import numpy as np
import pandas as pd
import orjson
import duckdb
import re

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Dict, Optional
from pathlib import Path
from functools import lru_cache
from fastapi import Depends

from api.state11 import cache # this is update to new high performance mapping for binary mode
from api.config.app_config import load_app_config
from api.v1_1.helper import parse_uri, discover_options, generate_output, discover_all
from api.v1_0.helper import generate_sql
from api.v1_1.helper import execute # this is update to new high performance execution for binary mode

from api.v1_1.plugin import load_indicator_plugins
from api.v1_0.version import API_VERSION


@lru_cache
def get_config():
    config_file = 'config.user.yaml' if Path('config.user.yaml').exists() else 'config.yaml'
    app_config = load_app_config(config_file)
    return app_config

# Setup router
router = APIRouter(
    prefix=f"/ohlcv/{API_VERSION}",
    tags=["ohlcv1_0"]
)

indicator_registry = load_indicator_plugins()

@router.get("/indicator/{name}/{request_uri:path}")
async def get_indicator(
    name: str,
    request_uri: str,
    limit: Optional[int] = Query(1440, gt=0, le=5000),
    offset: Optional[int] = Query(0, ge=0, le=1000),
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
    config=Depends(get_config),
):
    """
    Execute a registered indicator against OHLCV data and return the results.

    This endpoint resolves an indicator plugin by name, parses request options
    from the URI, retrieves the required market data, executes the indicator,
    and formats the output according to the requested mode (e.g., JSON, JSONP,
    binary, or MT4-compatible output).

    Args:
        name (str): Name of the registered indicator to execute.
        request_uri (str): Encoded URI containing data source and indicator options.
        limit (Optional[int]): Maximum number of rows to return.
        offset (Optional[int]): Offset into the result set.
        order (Optional[str]): Sort order for results ("asc" or "desc").
        callback (Optional[str]): JSONP callback function name.
        config: Application configuration dependency.

    Returns:
        Any: Formatted indicator output payload.

    Raises:
        HTTPException: If the indicator is not found.
        Exception: If execution fails or no output is produced.
    """
    try:
        # Ensure the requested indicator exists
        if name not in indicator_registry:
            raise HTTPException(status_code=404, detail="Indicator not found")

        # Track execution time
        time_start = time.time()

        # Parse request URI into structured options
        options = parse_uri(request_uri)

        # Inject pagination, ordering, callback, and output mode options
        options.update(
            {
                "limit": limit,
                "offset": offset,
                "order": order,
                "callback": callback,
                "fmode": config.http.fmode,
            }
        )

        # Expand and normalize derived options
        options = discover_options(options)

        # MT4 mode does not support multi-symbol or multi-timeframe queries
        if options.get("mt4") and len(options.get("select_data", [])) > 1:
            raise Exception(
                "Multi-symbol or multi-timeframe is not supported with MT4 flag"
            )

        # Resolve indicator plugin function
        plugin_func = indicator_registry[name]
        pos_opts = {}
        default_opts = {}

        # Extract positional argument mappings from the plugin, if defined
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            pos_opts.update(plugin_func.__globals__["position_args"](list(range(10))))
            default_opts.update(plugin_func.__globals__["position_args"]([]))

        # Build ordered positional argument list
        result = sorted(pos_opts, key=pos_opts.get)
        positional_opts = [name]
        for setting_name in result:
            val = options.get(setting_name, default_opts.get(setting_name))
            positional_opts.append(str(val))

        # Append indicator signature to select_data for cache/view resolution
        options["select_data"][0][4].append("_".join(positional_opts))

        # Acquire data using binary execution or SQL, depending on mode
        if options.get("fmode") == "binary":
            cache.register_views_from_options(options)
            df = execute(options)
        else:
            # I wonder if CSV input mode is still supported. I dont think so......
            df = cache.get_conn().sql(generate_sql(options)).df()

        # Prepare indicator options, including positional arguments
        ind_opts = options.copy()
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            ind_opts.update(plugin_func.__globals__["position_args"](positional_opts[1:]))

        # Determine sort columns and normalize ordering
        temp_sort = ["date", "time"] if "date" in df.columns else ["time"]
        df.sort_values(by=temp_sort, ascending=True, inplace=True)

        # Ensure numeric close values for indicator calculations
        if "close" in df.columns:
            df["close"] = pd.to_numeric(df["close"], errors="coerce")

        # Execute indicator logic and merge results with source data
        calculated_df = indicator_registry[name](df, ind_opts)
        enriched_df = df.join(calculated_df)

        # Apply final sorting order
        is_asc = options.get("order", "asc").lower() == "asc"
        enriched_df = (
            enriched_df.reset_index()
            .sort_values(by=temp_sort, ascending=is_asc)
        )

        # Apply binary-mode filters (time window and row limit)
        if options.get("fmode") == "binary":
            if options.get("after"):
                enriched_df = enriched_df[
                    enriched_df["time"] >= options["after"]
                ]
            if options.get("limit"):
                enriched_df = enriched_df.iloc[: options["limit"]]

        # Remove internal sorting column if present
        enriched_df = enriched_df.drop(columns=["sort_key"], errors="ignore")

        # Rebuild output columns, preserving indicator columns
        cols = [
            c
            for c in enriched_df.columns
            if c
            not in [
                "time",
                "sort_key",
                "year",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "index",
            ]
        ]
        if "time" in enriched_df.columns:
            cols.insert(2, "time")
        enriched_df = enriched_df[cols]

        # MT4-specific formatting: split datetime into date and time columns
        if options.get("mt4"):
            dt_series = pd.to_datetime(enriched_df["time"])
            enriched_df.insert(0, "date", dt_series.dt.strftime("%Y.%m.%d"))
            enriched_df["time"] = dt_series.dt.strftime("%H:%M:%S")

            # Remove unsupported MT4 columns
            cols = [
                c
                for c in enriched_df.columns
                if c not in ["symbol", "timeframe", "year"]
            ]
            enriched_df = enriched_df[cols]

        # Convert DataFrame to output payload
        columns = enriched_df.columns.tolist()
        results = enriched_df.values.tolist()

        # Update execution metadata
        options.update(
            {
                "indicator": name,
                "count": len(results),
                "wall": time.time() - time_start,
            }
        )

        # Generate final output
        output = generate_output(options, columns, results)
        if output:
            return output

        # Indicator produced no output
        raise Exception(f"{name} had no output")

    except Exception as e:
        # Build standardized error payload
        error_payload = {
            "status": "failure",
            "exception": str(e),
            "options": options,
        }

        # Return JSONP response if requested
        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload).decode()});",
                media_type="text/javascript",
            )

        # Default to JSON error response
        return JSONResponse(content=error_payload, status_code=400)
     


@router.get(f"/list/{{request_uri:path}}")
async def get_ohlcv_list(
    request_uri: str,
    callback: Optional[str] = "__bp_callback",
    config = Depends(get_config)
):
    """List available OHLCV symbols and timeframes.

    This endpoint parses a path-based request URI, discovers available
    filesystem-backed OHLCV data sources, and returns a mapping of symbols
    to their supported timeframes. The response can be returned as JSON
    or JSONP, depending on the requested output type.

    Args:
        request_uri (str): Path-encoded query string specifying output
            options (e.g., output format). Selection and temporal filters
            are ignored for this endpoint.
        callback (Optional[str]): JavaScript callback function name used
            when output_type is "JSONP". Defaults to "__bp_callback".

    Returns:
        dict | PlainTextResponse | JSONResponse:
        - A JSON object mapping symbols to lists of available timeframes
          when output_type is "JSON" or not specified.
        - A PlainTextResponse containing a JSONP payload when output_type
          is "JSONP".
        - A JSONResponse with error details and HTTP 400 status code on
          failure.

    Raises:
        Exception: Raised when an unsupported output type is requested
        (e.g., CSV), or when an internal error occurs during discovery.

    """
    # Parse the path-based request URI into structured query options
    options = parse_uri(request_uri)

    try:
        # Discover available OHLCV data sources from the filesystem
        available_data = discover_all(options)

        # Group timeframes by symbol name
        symbols = {}
        for ds in available_data:
            symbols.setdefault(ds.symbol, []).append(ds.timeframe)

        # Define 
        tf_order = {'m': 1, 'h': 60, 'd': 1440, 'W': 10080, 'M': 43200, 'Y': 525600}
        
        # Define sorting function
        def tf_sort_key(tf):
            match = re.match(r"(\d+)([a-zA-Z]+)", tf)
            if match:
                val, unit = match.groups()
                return int(val) * tf_order.get(unit, 1)
            return 0

        # Sort the timeframes for each symbol
        for symbol in symbols:
            symbols[symbol].sort(key=tf_sort_key)

        # Default JSON output
        if options.get("output_type") == "JSON" or options.get("output_type") is None:
            return {
                "status": "ok",
                "result": symbols,
            }

        # JSONP output for browser-based consumption
        if options.get("output_type") == "JSONP":
            payload = {
                "status": "ok",
                "result": symbols,
            }
            json_data = orjson.dumps(payload).decode("utf-8")
            return PlainTextResponse(
                content=f"{callback}({json_data});",
                media_type="text/javascript",
            )

        raise Exception("Unsupported content type (Sorry, CSV not supported)")

    except Exception as e:
        # Standardized error response
        error_payload = {"status": "failure", "exception": f"{e}","options": options}
        if options.get("output_type") == "JSONPX":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload)});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)
    pass

@router.get(f"/{{request_uri:path}}")
async def get_ohlcv(
    request_uri: str,
    limit: Optional[int] = Query(1440, gt=0, le=5000),
    offset: Optional[int] = Query(0, ge=0, le=1000),
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
    config=Depends(get_config),
):
    """
    Resolve a path-based OHLCV query and return time-series market data.

    This endpoint parses an encoded request URI describing symbols, timeframes,
    and data options, retrieves the corresponding OHLCV data, applies sorting
    and formatting rules, and returns the result in the requested output format.
    Special handling is applied for binary execution mode and MT4-compatible
    output.

    Args:
        request_uri (str): Encoded URI describing the OHLCV query.
        limit (Optional[int]): Maximum number of rows to return.
        offset (Optional[int]): Offset into the result set.
        order (Optional[str]): Sort order ("asc" or "desc").
        callback (Optional[str]): JSONP callback function name.
        config: Application configuration dependency.

    Returns:
        Any: Formatted OHLCV data payload.

    Raises:
        Exception: If validation fails or the output type is unsupported.
    """
    # Track request execution time
    time_start = time.time()

    # Parse the request URI into structured query options
    options = parse_uri(request_uri)

    # Inject pagination, ordering, callback, and output mode options
    options.update(
        {
            "limit": limit,
            "offset": offset,
            "order": order,
            "callback": callback,
            "fmode": config.http.fmode,
        }
    )

    try:
        # Normalize and expand derived options
        options = discover_options(options)

        # Validate MT4-specific constraints
        if options.get("mt4"):
            if len(options.get("select_data", [])) > 1:
                raise Exception(
                    "MT4 flag cannot handle multi-symbol/multi-timeframe selects"
                )
            if options.get("output_type") != "CSV":
                raise Exception("MT4 flag requires output/CSV")

        # Acquire data using binary execution or SQL, depending on mode
        if options.get("fmode") == "binary":
            cache.register_views_from_options(options)
            df = execute(options)
        else:
            # I dont think CSV input mode is still supported... we will find out soon
            sql = generate_sql(options)
            df = cache.get_conn().sql(sql).df()

        # Determine sort columns based on schema and apply ordering
        sort_cols = (
            ["date", "time", "symbol", "timeframe"]
            if "date" in df.columns
            else ["time", "symbol", "timeframe"]
        )
        is_asc = options.get("order", "asc").lower() == "asc"
        df = df.reset_index().sort_values(by=sort_cols, ascending=is_asc)

        # Reorder columns for backward compatibility
        cols = [
            c for c in df.columns if c not in ["time", "sort_key", "index", "year"]
        ]
        cols.insert(2, "time")
        cols.insert(2, "year")
        df = df[cols]

        # Apply MT4-specific output formatting
        if options.get("mt4"):
            # Convert time column to datetime for safe splitting
            df["time"] = pd.to_datetime(df["time"])

            # Split datetime into MT4-compatible date and time columns
            df.insert(0, "date", df["time"].dt.strftime("%Y.%m.%d"))
            df["time"] = df["time"].dt.strftime("%H:%M:%S")

            # Drop unsupported MT4 columns
            cols = [
                c
                for c in df.columns
                if c not in ["symbol", "timeframe", "year"]
            ]
            df = df[cols]

        # Prepare output payload
        columns = df.columns.tolist()
        results = df.values.tolist()

        # Attach metadata
        options["count"] = len(results)
        options["wall"] = time.time() - time_start

        # Generate and return formatted output
        output = generate_output(options, columns, results)
        if output:
            return output

        # No compatible output format found
        raise Exception("Unsupported content type")

    except Exception as e:
        # Build standardized error response
        error_payload = {
            "status": "failure",
            "exception": str(e),
            "options": options,
        }

        # Return JSONP error response if requested
        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload).decode()});",
                media_type="text/javascript",
            )

        # Default to JSON error response
        return JSONResponse(content=error_payload, status_code=400)






