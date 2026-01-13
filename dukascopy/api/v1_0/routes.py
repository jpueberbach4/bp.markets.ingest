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
from api.v1_0.helper import parse_uri, generate_sql, discover_options, generate_output, discover_all
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
    config = Depends(get_config)
):
    """Execute a registered indicator against OHLCV data and return results.

    This endpoint resolves a path-based OHLCV query, executes the corresponding
    SQL query against CSV-backed data sources, applies a registered indicator
    function, and returns the computed indicator output. Pagination, ordering,
    and output formatting are supported.

    Args:
        name (str): Name of the indicator to execute. Must exist in the
            ``indicator_registry``.
        request_uri (str): Path-encoded OHLCV query string specifying symbol
            selections, timeframes, temporal filters, and output options.
        limit (Optional[int]): Maximum number of rows to return. Defaults
            to 1440 and is constrained to the range 1–1440.
        offset (Optional[int]): Row offset for pagination. Defaults to 0
            and is constrained to the range 0–1000.
        order (Optional[str]): Sort order for results, either "asc" or "desc".
            Defaults to "asc".
        callback (Optional[str]): JavaScript callback function name used
            when output_type is "JSONP". Defaults to "__bp_callback".

    Returns:
        dict | PlainTextResponse | JSONResponse:
        - A JSON object or CSV payload containing indicator results.
        - A PlainTextResponse containing a JSONP payload when output_type
          is "JSONP".
        - A JSONResponse with error details and HTTP 400 status code on
          failure.

    Raises:
        HTTPException: If the requested indicator is not found.
        Exception: If query execution, indicator processing, or output
        generation fails.

    """
    try:
        if name not in indicator_registry:
            raise HTTPException(status_code=404, detail="Indicator not found")
        
        # Wall time
        time_start = time.time()  
        # Parse options
        options = parse_uri(request_uri)
        
        # Inject pagination, ordering, and callback parameters
        options.update(
            {
                "limit": limit,
                "offset": offset,
                "order": order,
                "callback": callback,
                "fmode": config.http.fmode
            }
        )

        # Discover options
        options = discover_options(options)

        if options.get('mt4') and len(options['select_data'])>1:
            raise Exception("Multi-symbol or multi-timeframe is not supported with MT4 flag")

        # We need to reconstruct indicator values
        plugin_func = indicator_registry[name]

        # We feed the position_args with dummy values and get a dict
        pos_opts = {}
        default_opts = {}
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            pos_opts.update(plugin_func.__globals__["position_args"]([0,1,2,3,4,5,6,7,8,9]))
            default_opts.update(plugin_func.__globals__["position_args"]([]))

        # Now we start constructing a string like bbands_12_5_9 ie (stupid stuff but oke)
        # Shouldnt have promised this update :|
        result = sorted(pos_opts, key=pos_opts.get)
       
        # We now have the order of the positional elements
        positional_opts = [name]
        for setting_name in result:
            if options.get(setting_name):
                positional_opts.append(options.get(setting_name))
            else:
                positional_opts.append(default_opts.get(setting_name))

        # we need to set the indicator string for execute to determine warmup rows
        options['select_data'][0][4].append('_'.join(positional_opts))
                
        if options.get("fmode") == "binary":
            # Get data efficiently in binary mode
            cache.register_views_from_options(options)
            df = execute(options)
        else:
            # Generate SQL (CSV-mode)
            sql = generate_sql(options)
            # Execute the SQL query in an in-memory DuckDB instance
            df = cache.get_conn().sql(sql).df()

        # Call the indicator
        ind_opts = options.copy()

        # Map positional arguments if plugin defines them
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            ind_opts.update(plugin_func.__globals__["position_args"](positional_opts[1:]))

        # Determine chronological sort order
        temp_sort = ['date', 'time'] if 'date' in df.columns else ['time']
        df.sort_values(by=temp_sort, ascending=True, inplace=True)

        # Ensure numeric type for 'close' column if it exists
        if 'close' in df.columns:
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
        
        # We call the indicator script here
        calculated_df = indicator_registry[name](df, ind_opts)

        # We join the calculated frame with the incoming dataframe
        enriched_df = df.join(calculated_df)

        # Sorting shit
        is_asc = options.get('order', 'asc').lower() == 'asc'
        enriched_df = enriched_df.reset_index().sort_values(by=temp_sort, ascending=is_asc)

        # I wonder if this still is compatible with CSV. We will find out.
        if options.get("fmode") == "binary":
            if options.get('after'):
                # Filter to keep only rows >= requested start time
                enriched_df = enriched_df[enriched_df['time'] >= options['after']]

            if options.get('limit'):
                # Limit rows
                enriched_df = enriched_df.iloc[:options['limit']]

        enriched_df = enriched_df.drop(columns=['sort_key'])

        # Backward compatability with CSV syntax before upgrade 1.0 API
        cols = [c for c in enriched_df.columns if c not in ['time','sort_key','year','open','high','low','close','volume','index']]
        cols.insert(2, 'time')
        enriched_df = enriched_df[cols]

        # Normalize columns and rows
        columns = enriched_df.columns.tolist()
        results = enriched_df.values.tolist()

        # Set back the indicator name
        options['indicator'] = name

        # Register wall-time
        options['count'] = len(results)
        options['wall'] = time.time() - time_start

        # Generate the output
        output = generate_output(options, columns, results)

        # If we have output, return the result
        if output:
            return output

        raise Exception(f"{name} had no output")
    except Exception as e:
        # Standardized error response
        error_payload = {"status": "failure", "exception": f"{e}","options": options}

        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload)});",
                media_type="text/javascript",
            )

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
    config = Depends(get_config)
):
    """Resolve a path-based OHLCV query and return time-series market data.

    This endpoint accepts a path-encoded query language describing
    symbol selections, timeframes, temporal filters, and output format.
    The request is translated into a DuckDB SQL query executed against
    CSV-backed OHLCV datasets.

    The response format is determined by the parsed output type and may
    be returned as JSON, JSONP, or CSV.

    Args:
        request_uri (str):
            Path-encoded query string defining symbol selections,
            filters, output format, and platform-specific options.
        limit (Optional[int]):
            Maximum number of records to return.
        offset (Optional[int]):
            Row offset for pagination.
        order (Optional[str]):
            Sort order for results, either `"asc"` or `"desc"`.
        callback (Optional[str]):
            JSONP callback function name when output type is JSONP.

    Returns:
        dict | PlainTextResponse | JSONResponse:
            A successful response contains OHLCV data formatted according
            to the requested output type. On failure, an error payload is
            returned with HTTP status code 400.
    """
    # Wall
    time_start = time.time()  
    # Parse the path-based request URI into structured query options
    options = parse_uri(request_uri)

    # Inject pagination, ordering, and callback parameters
    options.update(
        {
            "limit": limit,
            "offset": offset,
            "order": order,
            "callback": callback,
            "fmode": config.http.fmode
        }
    )

    try:
        # Discover options
        options = discover_options(options)

        # Handle MT4 cases
        if options.get("mt4") and len(options.get("select_data"))>1:
            raise Exception("MT4 flag cannot handle multi-symbol/multi-timeframe selects")

        if options.get("mt4") and options.get("output_type") != "CSV":
            raise Exception("MT4 flag requires output/CSV")

        if options.get("fmode") == "binary":
            # Get data efficiently in binary mode
            cache.register_views_from_options(options)
            df = execute(options)
        else:
            # Generate SQL (CSV-mode)
            sql = generate_sql(options)
            # Execute the SQL query in an in-memory DuckDB instance
            df = cache.get_conn().sql(sql).df()

        # Determine chronological sort order
        temp_sort = ['date', 'time'] if 'date' in df.columns else ['time']
        df.sort_values(by=temp_sort, ascending=True, inplace=True)

        cols = [c for c in df.columns if c not in ['time','sort_key','index','year']]
        cols.insert(2, 'time')
        cols.insert(2, 'year')
        df = df[cols]

        # Normalize columns and rows
        columns = df.columns.tolist()
        results = df.values.tolist()

        # Wall
        options['count'] = len(results)
        options['wall'] = time.time() - time_start
        # Generate the output
        output = generate_output(options, columns, results)

        # If we have output, return the result
        if output:
            return output

        # Unsupported output type
        raise Exception("Unsupported content type")

    except Exception as e:
        # Standardized error response
        error_payload = {"status": "failure", "exception": f"{e}","options": options}

        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload)});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)





