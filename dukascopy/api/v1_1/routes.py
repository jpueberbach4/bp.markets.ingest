#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        routes.py

Author:      JP Ueberbach
Created:     2026-01-12
Updated:     2026-01-15
             2026-01-23
             2026-02-08 Polars nativeness

FastAPI router implementing the public OHLCV query and indicator execution API.

This module exposes the HTTP interface for querying OHLCV (Open, High, Low,
Close, Volume) market data and executing technical indicators via a
path-based, slash-delimited query DSL. All endpoints are versioned and
available under the "/ohlcv/{version}" namespace.

The router is responsible for:
    - Parsing the encoded request URI into structured query options
    - Validating query constraints (pagination, ordering, output format)
    - Discovering available symbols, timeframes, and indicator plugins
    - Retrieving OHLCV data from the underlying data layer
    - Executing indicator logic and post-processing results
    - Serializing responses into JSON, JSONP, or CSV

Execution Model:
    - Incoming requests are parsed into an internal options dictionary
    - Data access and indicator execution are delegated to shared helpers
    - Polars is used as the internal execution engine for performance
    - Output formatting is handled centrally by helper utilities

Indicator System:
    - Indicators are discovered dynamically from the plugin registry
    - Metadata (defaults, warmup, descriptions) is exposed via list endpoints
    - Indicator execution is coordinated through the shared cache layer

Public Endpoints:
    - GET /ohlcv/{version}/{request_uri}
        Execute OHLCV queries and indicator calculations
    - GET /ohlcv/{version}/list/indicators/{request_uri}
        List available indicator plugins and their metadata
    - GET /ohlcv/{version}/list/symbols/{request_uri}
        List available symbols and supported timeframes

Notes:
    - This module is intended to be imported and registered with FastAPI
    - It is not designed to be executed as a standalone script

Requirements:
    - Python 3.8+
    - FastAPI
    - Pandas
    - Polars
    - orjson

License:
    MIT License
===============================================================================
"""

import time
import orjson
import re
import pandas as pd
import polars as pl

from fastapi import APIRouter, Query, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional
from pathlib import Path
from functools import lru_cache

from util.cache import MarketDataCache
from api.config.app_config import load_app_config
from api.v1_1.helper import parse_uri, discover_options, generate_output, _get_ms
from api.v1_1.version import API_VERSION
from util.api import get_data


@lru_cache
def get_config():
    """
    Load and cache the application configuration.

    The configuration file is resolved once and cached for the lifetime
    of the process. A user-specific configuration file is preferred when
    present; otherwise, the default configuration is loaded.

    Returns:
        object: Parsed application configuration object.
    """
    config_file = "config.user.yaml" if Path("config.user.yaml").exists() else "config.yaml"
    return load_app_config(config_file)


# Initialize the FastAPI router for versioned OHLCV endpoints
router = APIRouter(
    prefix=f"/ohlcv/{API_VERSION}",
    tags=["ohlcv1_0"],
)


@router.get("/list/indicators/{request_uri:path}")
async def list_indicators(
    request_uri: str,
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
    id: Optional[str] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    config=Depends(get_config),
):
    """
    List registered indicator plugins and their metadata.

    This endpoint parses the request URI to resolve output options, then
    retrieves metadata for all registered indicator plugins from the
    indicator registry. The result can be returned as JSON or JSONP.

    Wall-clock execution time is included in the response options.

    Args:
        request_uri (str): Path-encoded URI defining output options.
        order (Optional[str]): Sort order for the response ("asc" or "desc").
        callback (Optional[str]): JSONP callback function name.
        id (Optional[str]): Optional request identifier echoed in the response.
        symbol (Optional[str]): Optional symbol used for template resolution.
        timeframe (Optional[str]): Optional timeframe used for template resolution.
        config: Injected application configuration.

    Returns:
        dict | PlainTextResponse | JSONResponse:
            Successful responses include indicator metadata and options.
            Errors return a standardized failure payload.
    """
    # Record start time for wall-clock execution measurement
    time_start = time.time()

    # Parse the path-based request URI into structured options
    options = parse_uri(request_uri)

    # Inject runtime options that are not encoded in the URI
    options.update(
        {
            "callback": callback,
            "fmode": config.http.fmode,
        }
    )

    # Echo request id back to the client if provided
    if id:
        options["id"] = id

    try:
        # Initialize cache access layer
        cache = MarketDataCache()

        # Retrieve metadata for all registered indicator plugins
        data = cache.indicators.get_metadata_registry()

        # Resolve template strings in indicator defaults when symbol/timeframe is provided
        if symbol or timeframe:
            for indicator_name in data:
                for default_name in data[indicator_name]["defaults"]:
                    val = data[indicator_name]["defaults"][default_name]
                    data[indicator_name]["defaults"][default_name] = val.format(**locals())

        # Attach wall-clock execution time
        options["wall"] = time.time() - time_start

        callback = options.get("callback")

        # Default JSON output
        if options.get("output_type") in (None, "JSON"):
            return {
                "status": "ok",
                "options": options,
                "result": data,
            }

        # JSONP output for browser-based consumers
        if options.get("output_type") == "JSONP":
            payload = {
                "status": "ok",
                "options": options,
                "result": data,
            }
            json_data = orjson.dumps(payload).decode("utf-8")
            return PlainTextResponse(
                content=f"{callback}({json_data});",
                media_type="text/javascript",
            )

        # CSV output is intentionally not supported for indicator listings
        raise Exception("Unsupported content type (CSV not supported)")

    except Exception as e:
        # Log full traceback to the service console for debugging
        import traceback
        traceback.print_exc()

        # Standardized error payload
        error_payload = {
            "status": "failure",
            "exception": f"{e}",
            "options": options,
        }

        # JSONP error response
        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload).decode('utf-8')});",
                media_type="text/javascript",
            )

        # Default JSON error response
        return JSONResponse(content=error_payload, status_code=400)


@router.get("/list/symbols/{request_uri:path}")
async def get_ohlcv_list(
    request_uri: str,
    callback: Optional[str] = "__bp_callback",
    id: Optional[str] = None,
    config=Depends(get_config),
):
    """
    List available OHLCV symbols and their supported timeframes.

    This endpoint ignores selection and temporal filters and instead
    performs filesystem-backed discovery of available OHLCV datasets.
    Results are grouped by symbol and sorted by timeframe duration.

    Args:
        request_uri (str): Path-encoded URI defining output options.
        callback (Optional[str]): JSONP callback function name.
        id (Optional[str]): Optional request identifier echoed in the response.
        config: Injected application configuration.

    Returns:
        dict | PlainTextResponse | JSONResponse:
            Mapping of symbols to sorted timeframe lists, or an error payload.
    """
    # Parse request URI into structured options
    options = parse_uri(request_uri)

    # Echo request id back to the client if provided
    if id:
        options["id"] = id

    try:
        # Initialize cache access layer
        cache = MarketDataCache()

        # Discover all available datasets from the registry
        available_data = cache.registry.get_available_datasets()

        # Group discovered timeframes by symbol
        symbols = {}
        for ds in available_data:
            symbols.setdefault(ds.symbol, []).append(ds.timeframe)

        # Timeframe unit weights used for sorting (in minutes)
        tf_order = {
            "m": 1,
            "h": 60,
            "d": 1440,
            "W": 10080,
            "M": 43200,
            "Y": 525600,
        }

        # Convert timeframe strings (e.g. "15m", "4h") into sortable numeric values
        def tf_sort_key(tf):
            match = re.match(r"(\d+)([a-zA-Z]+)", tf)
            if match:
                val, unit = match.groups()
                return int(val) * tf_order.get(unit, 1)
            return 0

        # Sort timeframes for each symbol in ascending duration
        for symbol in symbols:
            symbols[symbol].sort(key=tf_sort_key)

        # Default JSON output
        if options.get("output_type") in (None, "JSON"):
            return {
                "status": "ok",
                "options": options,
                "result": symbols,
            }

        # JSONP output
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

        raise Exception("Unsupported content type (CSV not supported)")

    except Exception as e:
        # Log traceback for debugging
        import traceback
        traceback.print_exc()

        error_payload = {
            "status": "failure",
            "exception": f"{e}",
            "options": options,
        }

        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload).decode('utf-8')});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)


@router.get("/{request_uri:path}")
async def get_ohlcv(
    request_uri: str,
    limit: Optional[int] = Query(1440, gt=0, le=100000),
    offset: Optional[int] = Query(0, ge=0, le=100000),
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback",
    filename: Optional[str] = "data.csv",
    id: Optional[str] = None,
    subformat: Optional[int] = None,
    config=Depends(get_config),
):
    """
    Execute a path-based OHLCV query and return market data.

    This endpoint resolves the encoded request URI into structured query
    options, retrieves OHLCV data, applies indicator logic, and serializes
    the result into the requested output format.

    Internally, Polars is used as the execution engine for performance.
    Output formatting is delegated to shared helper utilities.

    Args:
        request_uri (str): Path-encoded OHLCV query DSL.
        limit (Optional[int]): Maximum number of rows to return.
        offset (Optional[int]): Row offset for pagination.
        order (Optional[str]): Sort order ("asc" or "desc").
        callback (Optional[str]): JSONP callback function name.
        filename (Optional[str]): Output filename when CSV is requested.
        id (Optional[str]): Optional request identifier.
        subformat (Optional[int]): Optional alternate JSON format selector.
        config: Injected application configuration.

    Returns:
        dict | PlainTextResponse | JSONResponse:
            Serialized OHLCV data or a standardized error payload.
    """
    # Record wall-clock start time
    time_start = time.time()

    # Parse the request URI into structured options
    options = parse_uri(request_uri)

    # Inject runtime query parameters and defaults
    options.update(
        {
            "limit": limit,
            "offset": offset,
            "order": order,
            "callback": callback,
            "fmode": config.http.fmode,
            "return_polars": True,  # Always request Polars for internal execution
        }
    )

    # Echo request id back to the client
    if id:
        options["id"] = id

    # Support alternate JSON output formats
    if subformat:
        options["subformat"] = subformat

    # Attach output filename for CSV responses
    if options.get("output_type") == "CSV":
        options["filename"] = filename

    try:
        # Enable profiling for performance diagnostics
        profiling_enabled = True
        if profiling_enabled:
            import cProfile, pstats, io
            pr = cProfile.Profile()
            pr.enable()

        # Resolve derived options (selects, indicators, modifiers)
        options = discover_options(options)

        # MT4 compatibility checks
        if options.get("mt4") and len(options.get("select_data")) > 1:
            raise Exception("MT4 flag does not support multi-select queries")

        if options.get("mt4") and options.get("output_type") != "CSV":
            raise Exception("MT4 flag requires CSV output")

        # Resolve temporal bounds and execution parameters
        after_ms = _get_ms(options.get("after", "1970-01-01 00:00:00"))
        until_ms = _get_ms(options.get("until", "3000-01-01 00:00:00"))
        limit = options.get("limit", 1000)
        order = options.get("order", "desc")

        # Disable recursive mapping for CSV and specific subformats
        disable_recursive_mapping = (
            options.get("output_type") == "CSV" or options.get("subformat") == 3
        )

        # Collect Polars DataFrames for each select clause
        select_df = []

        for item in options["select_data"]:
            # Unpack resolved select tuple
            symbol, timeframe, _, modifiers, indicators = item

            # Retrieve OHLCV data and indicators via internal API
            temp_df = get_data(
                symbol,
                timeframe,
                after_ms,
                until_ms,
                limit,
                order,
                indicators,
                {
                    "modifiers": modifiers,
                    "disable_recursive_mapping": disable_recursive_mapping,
                    "return_polars": True,
                },
            )

            # Accumulate results for multi-select queries
            select_df.append(temp_df)

        # Concatenate all result frames using Polars
        enriched_df = pl.concat(select_df)

        # Default sort order
        sort_columns = ["time_ms"]

        # Multi-select queries require additional sort keys
        if len(options["select_data"]) > 1:
            sort_columns = ["time_ms", "symbol", "timeframe"]

        # Apply final sorting
        enriched_df = enriched_df.sort(sort_columns, descending=(order != "asc"))

        # Apply row limit after sorting
        if options.get("limit"):
            enriched_df = enriched_df.head(options["limit"])

        # Attach response metadata
        options["count"] = len(enriched_df)
        options["wall"] = time.time() - time_start

        # Generate serialized output
        output = generate_output(enriched_df, options)

        if profiling_enabled:
            pr.disable()
            s = io.StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
            ps.print_stats(20)
            print(s.getvalue())

        if output:
            return output

        raise Exception("Unsupported content type")

    except Exception as e:
        # Log traceback for debugging
        import traceback
        traceback.print_exc()

        error_payload = {
            "status": "failure",
            "exception": f"{e}",
            "options": options,
        }

        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"{callback}({orjson.dumps(error_payload).decode('utf-8')});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)
