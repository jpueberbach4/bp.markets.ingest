#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        routes.py

Author:      JP Ueberbach
Created:     2026-01-12

FastAPI router implementing a versioned OHLCV and indicator execution API.

This module defines the public HTTP interface for querying OHLCV
(Open, High, Low, Close, Volume) time-series data and applying derived
technical indicators via a path-based, slash-delimited query DSL.
All endpoints are exposed under the "/ohlcv/{version}" namespace.

The API is designed for high-throughput, low-latency market data access
and supports both CSV-backed and memory-mapped binary datasets.

Key Features:
    - Executes OHLCV queries defined by a path-based DSL.
    - Discovers available symbols and timeframes from the filesystem.
    - Lists dynamically loaded indicator plugins with metadata.
    - Applies indicator plugins in parallel to resolved OHLCV data.
    - Supports pagination, ordering, temporal filters, and MT4-specific flags.
    - Returns output in multiple formats: JSON, JSONP, and CSV.
    - Includes execution timing (wall-clock) in response metadata.

Request Processing Pipeline:
    1. Parse the path-based DSL into structured query options.
    2. Validate pagination, ordering, output mode, and platform constraints.
    3. Resolve symbol/timeframe selections against filesystem-backed datasets.
    4. Register memory-mapped views for binary OHLCV sources (when enabled).
    5. Execute DuckDB queries against CSV or binary-backed data.
    6. Apply indicator plugins in parallel to the result set.
    7. Apply temporal filtering, row limits, and column normalization.
    8. Serialize results into the requested output format.

Indicator System:
    - Indicator plugins are dynamically loaded at application startup.
    - Each plugin must expose a `calculate(data, options)` callable.
    - Optional plugin metadata (defaults, warmup, description, meta) is
      introspected at runtime.
    - Indicator execution is parallelized for performance.

Special Endpoints:
    - `/list/indicators/{request_uri}`:
        Returns metadata for all registered indicator plugins.
    - `/quack`:
        Provides a playful “DuckDB experience” for demonstration and testing.

Usage:
    - This module is registered as part of the FastAPI router configuration.
    - It is not intended to be executed as a standalone script.

Primary Functions:
    - get_config(): Load and cache application configuration.
    - list_indicators(): Enumerate available indicator plugins.
    - get_ohlcv(): Resolve and execute path-based OHLCV queries.
    - quack(): Simulated full-table scan endpoint for testing.

Requirements:
    - Python 3.8+
    - FastAPI
    - DuckDB
    - NumPy
    - Pandas
    - orjson

License:
    MIT License
===============================================================================
"""

import time
import orjson

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional
from pathlib import Path
from functools import lru_cache
from fastapi import Depends

from api.state11 import cache
from api.config.app_config import load_app_config
from api.v1_1.helper import parse_uri, discover_options, generate_output, execute
from api.v1_1.parallel import parallel_indicators
from api.v1_1.plugin import indicator_registry, get_indicator_plugins
from api.v1_1.version import API_VERSION

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

@router.get(f"/quack")
async def quack_at_me():
    return quack()

@router.get(f"/list/indicators/{{request_uri:path}}")
async def list_indicators(
    request_uri: str,
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
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
    try:
        # Retrieve metadata for all registered indicators
        data = get_indicator_plugins(indicator_registry)

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

@router.get(f"/{{request_uri:path}}")
async def get_ohlcv(
    request_uri: str,
    limit: Optional[int] = Query(1440, gt=0, le=20000),
    offset: Optional[int] = Query(0, ge=0, le=20000),
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


        # In binary mode, we register MMap views            
        cache.register_views_from_options(options)

        # Execute data-engine
        df = execute(options)

        # Support for CSV output mode (do not build recursive output)
        disable_recursive_mapping = False
        if options.get("output_type") == "CSV":
            disable_recursive_mapping = True

        # Enrich the returned result with the requested indicators (parallelized)
        enriched_df = parallel_indicators(df, options, indicator_registry, disable_recursive_mapping)

        if options.get('after'):
            # Filter to keep only rows >= requested start time
            enriched_df = enriched_df[enriched_df['time'] >= options['after']]

        if options.get('limit'):
            # Limit rows
            enriched_df = enriched_df.iloc[:options['limit']]
        
        # Normalize columns and rows
        columns = enriched_df.columns.tolist()
        results = enriched_df.values.tolist()

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



def quack():
    # Recreate the authentic DuckDB experience
    import random
    import time
    time.sleep(0.04)
    quacks = [
        "QUACK! (translation: Have you tried a full-table scan?)",
        "QUACK! (translation: Let me just check every single row real quick...)",
        "QUACK! (translation: Binary search? Never heard of her.)",
        "QUACK! (translation: Your timestamp is somewhere in these 8 million rows. BRB!",
        "QUACK! (translation: Why go direct when you can go through ALL the data first?)"
    ]
    
    return {
        "status": "quacking",
        "message": random.choice(quacks),
        "performance": {
            "latency": "40ms (thoughtfully slow)",
            "records_scanned": "8,000,000 (all of them, just to be sure)",
            "optimization_level": "quacktimal",
            "efficiency": "0.0000125% (1 record / 8 million scanned)"
        },
        "suggestion": "For faster results, try literally any other endpoint.",
        "served_lag": 0.04
    }