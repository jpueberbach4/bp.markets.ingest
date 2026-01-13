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
from api.v1_1.helper import parse_uri, discover_options, generate_output, discover_all, execute_sql
from api.v1_1.parallel import parallel_indicators
from api.v1_1.plugin import load_indicator_plugins, indicator_registry
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

        profile = False

        if profile:
            import cProfile
            import pstats
            profiler = cProfile.Profile()
            profiler.enable()

        df = execute_sql(options)

        enriched_df = parallel_indicators(df, options, indicator_registry)

        if options.get('after'):
            # Filter to keep only rows >= requested start time
            enriched_df = enriched_df[enriched_df['time'] >= options['after']]

        if options.get('limit'):
            # Limit rows
            enriched_df = enriched_df.iloc[:options['limit']]
        

        columns = enriched_df.columns.tolist()
        results = enriched_df.values.tolist()

        if profile:
            profiler.disable()
            import io
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(30)

            print(s.getvalue())

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



