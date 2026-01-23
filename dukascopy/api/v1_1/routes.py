#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        routes.py

Author:      JP Ueberbach
Created:     2026-01-12
Updated:     2026-01-15
             2026-01-23

FastAPI router implementing a versioned OHLCV query and indicator execution API.

This module defines the public HTTP interface for querying OHLCV
(Open, High, Low, Close, Volume) time-series market data and applying
derived technical indicators using a path-based, slash-delimited query
DSL. All endpoints are exposed under the "/ohlcv/{version}" namespace.

The router translates encoded request URIs into structured query options,
discovers available datasets and indicators, executes data retrieval,
applies indicator logic, and serializes results into the requested
output format.

Key Features:
    - Path-based DSL for expressing OHLCV queries and indicator selection
    - Filesystem-backed discovery of symbols and supported timeframes
    - Integration with a dynamic indicator plugin registry
    - Pagination, ordering, temporal filtering, and MT4 compatibility
    - Multiple output formats: JSON, JSONP, and CSV
    - Wall-clock execution timing included in response metadata

Request Processing Pipeline:
    1. Parse the path-based DSL into structured query options
    2. Validate pagination, ordering, output mode, and platform constraints
    3. Discover symbol/timeframe selections from filesystem-backed datasets
    4. Retrieve OHLCV data via the configured data access layer
    5. Apply indicator plugins to the result set
    6. Apply temporal filtering, row limits, and column normalization
    7. Serialize results into the requested output format

Indicator System:
    - Indicator plugins are dynamically loaded at application startup
    - Plugin metadata (defaults, warmup, description, meta) is exposed
      via discovery endpoints
    - Indicator execution is coordinated through the shared cache layer

Public Endpoints:
    - GET /ohlcv/{version}/{request_uri}:
        Execute OHLCV queries and indicator calculations
    - GET /ohlcv/{version}/list/indicators/{request_uri}:
        Enumerate available indicator plugins and metadata
    - GET /ohlcv/{version}/list/symbols/{request_uri}:
        List available symbols and supported timeframes

Usage:
    - This module is registered as part of the FastAPI router configuration
    - It is not intended to be executed as a standalone script

Requirements:
    - Python 3.8+
    - FastAPI
    - Pandas
    - orjson

License:
    MIT License
===============================================================================
"""

import time
import orjson
import re
import pandas as pd

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional
from pathlib import Path
from functools import lru_cache
from fastapi import Depends

from util.cache import cache
from api.config.app_config import load_app_config
from api.v1_1.helper import parse_uri, discover_options, generate_output, _get_ms
from api.v1_1.version import API_VERSION

from util.api import get_data

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

@router.get(f"/list/indicators/{{request_uri:path}}")
async def list_indicators(
    request_uri: str,
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
    id: Optional[str] = None, 
    config=Depends(get_config),
):
    """
    List registered indicator plugins with optional output formatting.

    This endpoint resolves a path-based request URI, collects metadata for all
    registered indicator plugins, and returns the result in the requested
    output format (JSON or JSONP). Execution timing information is included
    in the response options.

    Args:
        request_uri (str): Encoded URI specifying output options and format.
        order (Optional[str]): Sort order for the response ("asc" or "desc").
        callback (Optional[str]): JSONP callback function name.
        config: Application configuration dependency.

    Returns:
        dict or PlainTextResponse: A payload containing indicator metadata and
        request options, formatted as JSON or JSONP depending on the request.

    Raises:
        Exception: If indicator metadata retrieval or response generation fails.
    """
    # Track execution start time for wall-clock measurement
    time_start = time.time()

    # Parse the path-based request URI into structured options
    options = parse_uri(request_uri)

    # Inject callback and output mode from configuration
    options.update(
        {
            "callback": callback,
            "fmode": config.http.fmode,
        }
    )
    
    # If an id was passed on the URL, return it in response
    if id: options['id'] = id

    try:
        # Retrieve metadata for all registered indicators
        data = cache.indicators.get_metadata_registry()

        # Record wall-clock execution time
        options["wall"] = time.time() - time_start

        # Resolve callback name from options
        callback = options.get("callback")

        # Default JSON output
        if options.get("output_type") == "JSON" or options.get("output_type") is None:
            return {
                "status": "ok",
                "options": options,
                "result": data,
            }

        # JSONP output for browser-based consumption
        if options.get("output_type") == "JSONP":
            payload = {
                "status": "ok",
                "options": options,
                "result": data,
            }

            # Serialize payload and wrap in callback function
            json_data = orjson.dumps(payload).decode("utf-8")
            return PlainTextResponse(
                content=f"{callback}({json_data});",
                media_type="text/javascript",
            )

        raise Exception("Unsupported content type (Sorry, CSV not supported)")
        
    except Exception as e:
        # Print traceback in service console in case developer makes a mistake
        import traceback
        traceback.print_exc()
        # Build standardized error payload
        error_payload = {
            "status": "failure",
            "exception": f"{e}",
            "options": options,
        }

        # Return JSONP error response if requested
        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload)});",
                media_type="text/javascript",
            )

        # Default to JSON error response
        return JSONResponse(content=error_payload, status_code=400)


@router.get(f"/list/symbols/{{request_uri:path}}")
async def get_ohlcv_list(
    request_uri: str,
    callback: Optional[str] = "__bp_callback",
    id: Optional[str] = None, 
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
    # If an id was passed on the URL, return it in response
    if id: options['id'] = id

    try:
        # Discover available OHLCV data sources from the filesystem
        available_data = cache.registry.get_available_datasets()

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
                "options": options,
                "result": symbols,
            }

        # JSONP output for browser-based consumption
        if options.get("output_type") == "JSONP":
            payload = {
                "status": "ok",
                "options": options,
                "result": symbols,
            }
            json_data = orjson.dumps(payload).decode("utf-8")
            return PlainTextResponse(
                content=f"{callback}({json_data});",
                media_type="text/javascript",
            )

        raise Exception("Unsupported content type (Sorry, CSV not supported)")

    except Exception as e:
        # Print traceback in service console in case developer makes a mistake
        import traceback
        traceback.print_exc()
        # Standardized error response
        error_payload = {"status": "failure", "exception": f"{e}","options": options}
        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload)});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)
    pass

@router.get(f"/{{request_uri:path}}")
async def get_ohlcv(
    request_uri: str,
    limit: Optional[int] = Query(1440, gt=0, le=100000),
    offset: Optional[int] = Query(0, ge=0, le=100000),
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
    filename: Optional[str] = "data.csv",
    id: Optional[str] = None, 
    subformat: Optional[int] = None, 
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
            "fmode": config.http.fmode,
        }
    )

    # If an id was passed on the URL, return it in response
    if id: options['id'] = id
    # Support for alternate JSON version
    if subformat: options['subformat'] = subformat
    # If CSV mode, get output filename from query url
    if options.get('output_type') == "CSV": options['filename'] = filename

    try:
        # Discover options
        options = discover_options(options)

        # Handle MT4 cases
        if options.get("mt4") and len(options.get("select_data"))>1:
            raise Exception("MT4 flag cannot handle multi-symbol/multi-timeframe selects")

        if options.get("mt4") and options.get("output_type") != "CSV":
            raise Exception("MT4 flag requires output/CSV")

        # Get default settings
        after_ms = _get_ms(options.get('after', '1970-01-01 00:00:00'))
        until_ms = _get_ms(options.get('until', '3000-01-01 00:00:00'))
        limit = options.get('limit', 1000)
        order = options.get('order', 'desc')

        # Output option CSV and subformat 3 require disabled recursive_mapping
        disable_recursive_mapping= False
        if options.get("output_type") == "CSV" or options.get("subformat") == 3:
            odisable_recursive_mapping = True

        # Dataframe array
        select_df = []

        for item in options['select_data']:

            # Retrieve the arguments from resolved select_data
            symbol, timeframe, _, modifiers, indicators = item
            
            # Call the new internal get_data functionality
            temp_df = get_data(
                symbol, timeframe, 
                after_ms, until_ms, 
                limit, order, indicators, 
                {
                    "modifiers": modifiers,                                 # eg skiplast
                    "disable_recursive_mapping": disable_recursive_mapping  # disables recursive mapping to dicts
                }
            )

            # Append dataframe for multiselect
            select_df.append(temp_df)


        # Join the dataframe array
        enriched_df = pd.concat(select_df, ignore_index=True, copy=False)

        # Default, we sort on sort_key (thats what it is for)
        sort_columns = ['sort_key']

        # In case of multi-selects, we need to sort by sort_key, symbol and timeframe
        if len(options['select_data'])>1: sort_columns = ['sort_key','symbol','timeframe']
        
        # Apply the final sorting
        if order == "asc":
            enriched_df.sort_values(by=sort_columns, ascending=True, inplace=True)
        else:
            enriched_df.sort_values(by=sort_columns, ascending=False, inplace=True)            

        if options.get('limit'):
            # Limit rows
            enriched_df = enriched_df.iloc[:options['limit']]

        # Wall
        options['count'] = len(enriched_df)
        options['wall'] = time.time() - time_start
        
        # Generate the output
        output = generate_output(enriched_df, options)

        # If we have output, return the result
        if output:
            return output

        # Unsupported output type
        raise Exception("Unsupported content type")

    except Exception as e:
        # Print traceback in service console in case developer makes a mistake
        import traceback
        traceback.print_exc()

        # Standardized error response
        error_payload = {"status": "failure", "exception": f"{e}","options": options}

        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload)});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)
