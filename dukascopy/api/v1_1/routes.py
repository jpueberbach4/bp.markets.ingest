"""
===============================================================================
File:        routes.py

Author:      JP Ueberbach
Created:     2026-01-12

FastAPI router implementing a versioned OHLCV and indicator API.

This module defines the public HTTP API for accessing OHLCV
(Open, High, Low, Close, Volume) time-series data and derived indicators
via a path-based query DSL. It exposes endpoints under the "/ohlcv/{version}" 
namespace.

Key Features:
    - Executes raw OHLCV queries using a slash-delimited query DSL.
    - Lists available symbols and timeframes discovered from the filesystem.
    - Executes dynamically loaded indicator plugins on resolved OHLCV data.
    - Supports pagination, ordering, and platform-specific options (e.g., MT4).
    - Returns output in multiple formats: JSON, JSONP, and CSV.

Request Processing Pipeline:
    1. Parse the path-based DSL into structured query options.
    2. Validate pagination, ordering, and output constraints.
    3. Resolve requested symbol/timeframe selections against filesystem-backed OHLCV data.
    4. Register memory-mapped views for selected datasets (binary file mode).
    5. Execute queries against CSV or binary sources.
    6. Apply indicator plugins in parallel to the query results.
    7. Filter, limit, and normalize rows based on user parameters.
    8. Serialize results into the requested output format.

Indicator System:
    - Dynamically loads indicator modules at startup.
    - Modules must expose a `calculate(data, options)` callable.
    - Supports parallel execution for improved performance.

Special Endpoints:
    - `/quack`: Provides a playful “DuckDB experience” for demonstration and testing.

Usage:
    - This module is included in the FastAPI router configuration.
    - It should not be executed directly as a standalone script.

Classes/Functions:
    - get_config(): Load the application configuration with caching.
    - get_ohlcv(): Main path-based OHLCV query endpoint.
    - quack(): Playful endpoint simulating full-table scan latency.

Requirements:
    - Python 3.8+
    - FastAPI
    - DuckDB
    - NumPy
    - Pandas
    - orjson (for JSON serialization)

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

from api.state11 import cache
from api.config.app_config import load_app_config
from api.v1_1.helper import parse_uri, discover_options, generate_output, discover_all, execute
from api.v1_1.parallel import parallel_indicators
from api.v1_1.plugin import load_indicator_plugins, indicator_registry, get_indicator_plugins
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

@router.get(f"/list/indicators")
async def list_indicators():
    return get_indicator_plugins(indicator_registry)


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


        # In binary mode, we register MMap views            
        cache.register_views_from_options(options)

        # Execute data-engine
        df = execute(options)

        # Enrich the returned result with the requested indicators (parallelized)
        enriched_df = parallel_indicators(df, options, indicator_registry)

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