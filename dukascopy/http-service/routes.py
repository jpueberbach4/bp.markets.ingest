#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        routes.py
 Author:      JP Ueberbach
 Created:     2026-01-02
 Description: FastAPI router implementing a path-based OHLCV query API.

              This module exposes a versioned `/ohlcv/{version}/*` catch-all
              endpoint that accepts a path-encoded query DSL for requesting
              OHLCV (Open, High, Low, Close, Volume) time-series data.

              Requests are processed by:
              
              - Parsing the path-based DSL into structured query options
              - Validating and applying pagination and ordering parameters
              - Resolving requested symbol/timeframe selections against
                filesystem-backed OHLCV data
              - Translating resolved options into a DuckDB SQL query
              - Executing the query against CSV sources using an in-memory
                DuckDB instance

              The API supports multiple output formats, including JSON,
              JSONP, and CSV, selected via the query DSL. Pagination is
              offset-based.

              The path-based DSL intentionally mirrors the syntax of the
              internal builder, ensuring full compatibility and making the
              API intuitive for users already familiar with the builder
              workflow.

 Usage:
     Included as part of the FastAPI application router configuration.

 Requirements:
     - Python 3.8+
     - FastAPI
     - DuckDB

 License:
     MIT License
===============================================================================
"""

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Dict, Optional
from helper import parse_uri
from version import API_VERSION
import io
import csv
import duckdb
import orjson

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Setup router
router = APIRouter(
    prefix="/ohlcv",
    tags=["ohlcv"]
)

@router.get(f"/{API_VERSION}/{{request_uri:path}}")
async def get_ohlcv(
    request_uri: str,
    limit: Optional[int] = Query(1000, gt=0, le=1000),
    offset: Optional[int] = Query(1, ge=0, le=1000),
    order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    callback: Optional[str] = "__bp_callback"
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
    # Parse the path-based request URI into structured query options
    options = parse_uri(request_uri)

    # Inject pagination, ordering, and callback parameters
    options.update(
        {
            "limit": limit,
            "offset": offset,
            "order": order,
            "callback": callback,
        }
    )

    # Import builder utilities for resolving file-backed OHLCV selections
    from builder.helper import resolve_selections, get_available_data_from_fs
    from builder.config.app_config import load_app_config

    try:
        # Load builder configuration
        config = load_app_config("config.user.yaml")

        # Discover available OHLCV data sources from the filesystem
        available_data = get_available_data_from_fs(config.builder)

        # Resolve requested selections against available data
        options["select_data"] = resolve_selections(
            options["select_data"], available_data, False
        )[0]

        # Generate a DuckDB-compatible SQL query from resolved options
        sql = generate_sql(options)

        # Execute the SQL query in an in-memory DuckDB instance
        with duckdb.connect(database=":memory:") as con:
            rel = con.sql(sql)
            results = rel.fetchall()
            columns = rel.columns

            # Default JSON output
            if options.get("output_type") == "JSON" or options.get("output_type") is None:
                return {
                    "status": "ok",
                    "result": [dict(zip(columns, row)) for row in results],
                }

            # JSONP output for browser-based consumption
            if options.get("output_type") == "JSONP":
                payload = {
                    "status": "ok",
                    "result": [dict(zip(columns, row)) for row in results],
                }
                json_data = orjson.dumps(payload).decode("utf-8")
                return PlainTextResponse(
                    content=f"{callback}({json_data});",
                    media_type="text/javascript",
                )

            # CSV output for file-based or analytical workflows
            if options.get("output_type") == "CSV":
                output = io.StringIO()
                if results:
                    dict_results = [dict(zip(columns, row)) for row in results]
                    writer = csv.DictWriter(output, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(dict_results)

                return PlainTextResponse(
                    content=output.getvalue(),
                    media_type="text/csv",
                )

            # Unsupported output type
            raise Exception("Unsupported content type")

    except Exception as e:
        # Standardized error response
        error_payload = {"status": "failure", "exception": f"{e}"}

        if options.get("output_type") == "JSONP":
            return PlainTextResponse(
                content=f"__callback({json.dumps(error_payload)});",
                media_type="text/javascript",
            )

        return JSONResponse(content=error_payload, status_code=400)



def generate_sql(options):
    """Generate a DuckDB SQL query for retrieving OHLCV data from CSV sources.

    This function constructs a SQL query based on parsed query options,
    including symbol/timeframe selections, temporal filters, modifiers,
    ordering, and pagination. Each selection is translated into an
    individual SELECT statement, which are then combined using
    `UNION ALL` and wrapped in a final ordered, paginated query.

    Args:
        options (dict):
            Parsed query options containing:
            
            - select_data (list[tuple]):
                Tuples of the form
                (symbol, timeframe, input_filepath, modifiers).
            - after (str, optional):
                Inclusive lower timestamp bound (ISO-8601–like).
            - until (str, optional):
                Exclusive upper timestamp bound.
            - order (str, optional):
                Sort order, either "asc" or "desc".
            - limit (int, optional):
                Maximum number of rows to return.
            - offset (int, optional):
                Row offset for pagination.

    Returns:
        str:
            A complete DuckDB-compatible SQL query string.
    """
    # Collect individual SELECT statements (one per symbol/timeframe/file)
    select_sql_array = []

    for item in options['select_data']:
        # Unpack select tuple and append global temporal filters
        symbol, timeframe, input_filepath, modifiers, after, until = (
            item + tuple([options.get('after'), options.get('until')])
        )

        # Columns selected from each CSV file, including normalized metadata
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

        # Base temporal filter applied to all selections
        where_clause = f"""
            WHERE time >= TIMESTAMP '{after}'
            AND time < TIMESTAMP '{until}'
        """

        # Optional modifier: exclude the most recent candle
        # Useful when the latest bar may still be forming
        if "skiplast" in modifiers:
            where_clause += (
                f" AND time < ("
                f"SELECT MAX(time) "
                f"FROM read_csv_auto('{input_filepath}')"
                f")"
            )

        # Construct SELECT statement for this specific CSV input
        select_sql = f"""
            SELECT
                {select_columns}
            FROM read_csv_auto('{input_filepath}')
            {where_clause}
        """

        select_sql_array.append(select_sql)

    # Columns selected from the UNIONed result set
    # (time is formatted back to string form for output)
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

    # Final ordering and pagination parameters with defaults
    order = options.get('order') if options.get('order') else "asc"
    limit = options.get('limit') if options.get('limit') else 100
    offset = options.get('offset') if options.get('offset') else 0

    # Combine all SELECTs, apply ordering and pagination
    select_sql = f"""
        SELECT {select_columns}
        FROM (
            {' UNION ALL '.join(select_sql_array)}
        )
        ORDER BY time {order}, symbol ASC, timeframe ASC
        LIMIT {limit} OFFSET {offset};
    """

    return select_sql

