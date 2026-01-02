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
from fastapi import APIRouter, HTTPException, Query, status
from typing import Dict, Optional
from helper import parse_uri
from version import API_VERSION
import duckdb

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Setup router
router = APIRouter(
    prefix="/ohlcv",
    tags=["ohlcv"]
)

# Setup catch-all /ohlcv/1.0/* route, this is dummy impl atm
@router.get(f"/{API_VERSION}/{{request_uri:path}}", response_model=Dict)
async def get_ohlcv(
    request_uri: str,
    limit: Optional[int] = Query(1000, gt=0, le=1000),          # TODO: from config (max_page * max_per_page)
    offset: Optional[int] = Query(1, ge=1, le=1000),            # TODO: from config (max_page)
    order: Optional[str] = Query("asc", regex="^(asc|desc)$")
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

    Returns:
        Dict:
            A dictionary containing the requested OHLCV data and
            associated metadata.

        TODO: strongly typed response
    """
    #
    # http://localhost:8000/ohlcv/1.0/select/SYMBOL:test,TF1,TF2:skiplast:test/ \
    # select/SYMBOL,TF1/after/2025-01-01+00:00:00/output/CSV/MT4?page=1&order=asc&limit=1000

    # Parse REQUEST_URI (path)
    options = parse_uri(request_uri)

    # Add the limit, page and order
    options.update(
        {
            "limit": limit,
            "offset": offset,
            "order": order
        }
    )

    """
    {
        "selections": [
            "SYMBOL:test/TF1,TF2:skiplast:test",
            "SYMBOL/TF1"
        ],
        "after": "2025-01-01 00:00:00",
        "output_format": "CSV",
        "platform": "MT4",
        "options": [],
        "limit": 1000,
        "page": 1,
        "order": "asc"
    }
    Looks good. Commit.
    Todo: make exactly comptible
    """

    # We are now setup for path resolution to select files (see if can re-use builder code)
    from builder.helper import resolve_selections, get_available_data_from_fs
    from builder.config.app_config import load_app_config

    try:
        # Load config from builder
        config = load_app_config('config.user.yaml')

        # Resolve available data
        available_data = get_available_data_from_fs(config.builder)

        # Resolve selections
        options['select_data'] = resolve_selections(options['select_data'], available_data, False)[0]

        # Generate SQL
        sql = generate_sql(options)

        # Execute the SQL statement

        with duckdb.connect(database=":memory:") as con:
            rel = con.sql(sql)
            results = rel.fetchall()
            columns = rel.columns
            return {
                "status":"ok",
                "result": [dict(zip(columns, row)) for row in results]
            }

    except Exception as e:
        return {
            "status": "failure",
            "exception": f"{e}"
        }
    return options


def generate_sql(options):
    select_sql_array = []
    for item in options['select_data']:
        symbol, timeframe, input_filepath, modifiers, after, until = \
            item + tuple([options.get('after'), options.get('until')])

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

        where_clause = f"""
            WHERE time >= TIMESTAMP '{after}'
            AND time < TIMESTAMP '{until}'
        """

        # Optional modifier: skip the latest timestamp
        if "skiplast" in modifiers:
            where_clause += (
                f" AND time < ("
                f"SELECT MAX(time) "
                f"FROM read_csv_auto('{input_filepath}')"
                f")"
            )

        select_sql = f"""
            SELECT 
                {select_columns} 
                FROM read_csv_auto('{input_filepath}')
                {where_clause}
        """

        select_sql_array.append(select_sql)

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

    order = options.get('order') if options.get('order') else "asc"
    limit = options.get('limit') if options.get('limit') else 100
    offset = options.get('offset') if options.get('offset') else 0

    select_sql = f"""
        SELECT {select_columns} 
        FROM (
            {' UNION ALL '.join(select_sql_array)}
        )
        ORDER BY time {order}, symbol ASC, timeframe ASC 
        LIMIT {limit} OFFSET {offset};
    """

    return select_sql
