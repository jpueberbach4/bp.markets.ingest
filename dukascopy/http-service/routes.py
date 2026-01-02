#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        routes.py
 Author:      JP Ueberbach
 Created:     2026-01-02
 Description: FastAPI router for OHLCV data access using a path-based query DSL.

              This module defines a versioned `/ohlcv/{version}/*` catch-all
              endpoint that accepts a path-encoded query language for
              requesting OHLCV (Open, High, Low, Close, Volume) time-series
              data.

              The endpoint is responsible for:
              
              - Accepting and validating pagination and ordering parameters
              - Parsing a path-based DSL describing symbols, timeframes,
                filters (after/until), output format, and platform options
              - Acting as an integration point for backend query execution
                (e.g., DuckDB), which is currently a placeholder

              Pagination is offset-based. Since financial time-series data
              may change over time, clients can use the `until` parameter
              to stabilize result sets across requests.

              NOTE:
              This module currently contains a dummy implementation and
              returns a placeholder response. Query parsing, execution,
              and strongly typed responses will be added incrementally.

 Usage:
     Included as part of the FastAPI application router configuration.

 Requirements:
     - Python 3.8+
     - FastAPI

 License:
     MIT License
===============================================================================
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict
from version import API_VERSION

# Setup router
router = APIRouter(
    prefix="/ohlcv",
    tags=["ohlcv"]
)

# Setup catch-all /ohlcv/1.0/* route, this is dummy impl atm
@router.get(f"/{API_VERSION}/{{path_str:path}}", response_model=Dict)
async def get_ohlcv(
    path_str: str,
    limit: int = Query(1000, gt=0, le=1_000_000), # TODO: from config (max_page * max_per_page)
    page: int = Query(1, ge=1, le=1000),          # TODO: from config (max_page)
    order: str = Query("asc", regex="^(asc|desc)$"),
    after: Optional[str] = None,
    until: Optional[str] = None
):
    """Retrieve OHLCV time-series data using a path-based query DSL.

    This endpoint parses a path-encoded query language to determine
    symbol selection, timeframes, output format, and platform-specific
    options (e.g., MT4). Internally, it builds and executes a DuckDB
    query and returns the resulting OHLCV data.

    Example URL structure:
        /ohlcv/1.0/select/SYMBOL,TF1,TF2:skiplast/select/SYMBOL,TF1/
        after/2025-01-01+00:00:00/output/CSV/MT4
        ?page=1&order=asc&limit=1000

    Pagination is offset-based. Since new candles may be created over
    time, page boundaries can shift when ordering by descending time.
    Clients can use the `until` parameter to stabilize result sets.

    Args:
        path_str (str):
            Path-encoded query string defining selections, filters,
            output format, and platform options.
        limit (int):
            Maximum number of records per page. Must be greater than 0
            and less than or equal to limits.max_page * limits.max_per_page.
        page (int):
            Page number for pagination (1-based index).
        order (str):
            Sort order for results. Must be either `"asc"` or `"desc"`.
        after (Optional[str]):
            Timestamp indicating the lower bound (inclusive)
            for returned candles.
        until (Optional[str]):
            Timestamp indicating the upper bound (exclusive)
            for returned candles. Useful for preventing page shifts
            as new data is added.

    Returns:
        Dict:
            A dictionary containing the requested OHLCV data and
            associated metadata.

        TODO: strongly typed response
    """
    # parse string for SELECT, AFTER, UNTIL, OUTPUT and MT4 
    # http://host:port/ohlcv/1.0/select/SYMBOL,TF1,TF2:skiplast/select/ \
    # SYMBOL,TF1/after/2025-01-01+00:00:00/output/CSV/MT4 \
    # ?page=1&order=asc|desc&limit=1000
    # select files to evaluate
    # construct DuckDB SQL query
    # execute DuckDB SQL query
    # construct response
    # return response
    # Note: we don't implement a result-id, if user wants to prevent that
    #       pages shift (eg on order descending) because new candles get created, 
    #       the user can use "until"
    return dict({"test":f"{path_str}"})
