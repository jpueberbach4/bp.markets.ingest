#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        args.py
 Author:      JP Ueberbach
 Created:     2025-12-30
 Version:     PUBLIC BETA
 Description: Panama rollover adjustment utilities for Dukascopy data processing.

              This module provides helper functions to fetch, normalize, cache, 
              and apply Panama-style rollover adjustments to Dukascopy time-series
              data. It is used as part of a batch extraction and resampling pipeline 
              to ensure continuous, back-adjusted price series across contract 
              rollovers.

              The module includes functionality for:
              - Fetching and caching rollover calendars from Dukascopy
              - Normalizing JSON/JSONP rollover data into CSV format
              - Applying cumulative rollover adjustments using DuckDB
              - Preparing extraction tasks that require Panama-adjusted data

Requirements:
    Python 3.8+
    duckdb
    requests
    filelock

License:
    MIT License
"""
import duckdb
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from pathlib import Path
import requests
import time
import json
import csv
import io
import re

CACHE_MAX_AGE = 86400
CACHE_PATH = "data/rollover" # Todo: public beta version

# Dukascopy CSV schema: column names and types
DUKASCOPY_CSV_SCHEMA = {
    "time": "TIMESTAMP",
    "open": "DOUBLE",
    "high": "DOUBLE",
    "low": "DOUBLE",
    "close": "DOUBLE",
    "volume": "DOUBLE",
}

# Standard CSV timestamp format for parsing
CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

def normalize_data(data: str, symbol: str) -> Optional[str]:
    """Normalize rollover adjustment data into CSV format.

    This function converts a JSON or JSONP response containing rollover
    adjustment information into a normalized CSV string. The data is filtered
    by symbol, sorted chronologically, and formatted for downstream ingestion
    (e.g., by DuckDB).

    Args:
        data (str): Raw response payload, potentially wrapped as JSONP.
        symbol (str): Symbol identifier used to filter relevant rows.

    Returns:
        Optional[str]: A CSV-formatted string containing normalized rollover
        data for the symbol, or None if no matching data is found or parsing
        fails.
    """

    # Remove leading and trailing whitespace from the response
    data = data.strip()

    # Unwrap JSONP payload if present
    if data.startswith("_callbacks____qmjn9av6ydd"):
        match = re.search(r"_callbacks____qmjn9av6ydd\((.*)\)", data, re.DOTALL)
        if match:
            data = match.group(1)
        else:
            return None

    # Parse the JSON content
    json_data = json.loads(data)

    if json_data:
        # Normalize symbol format to match API title field
        symbol = "/".join(symbol.rsplit("-", 1))

        # Prepare an in-memory buffer for CSV output
        sio = io.StringIO()

        # Filter rows that match the requested symbol
        json_data = [
            row
            for row in json_data
            if str(row.get("title", "")).strip().casefold()
            == symbol.strip().casefold()
        ]

        # Abort if no rows match the symbol
        if not json_data:
            return None

        # Sort rows chronologically by rollover date
        json_data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%b-%y"))

        # Build CSV headers with date first
        headers = ["date"] + [k for k in json_data[0].keys() if k != "date"]

        # Write normalized rows to CSV buffer
        writer = csv.DictWriter(sio, fieldnames=headers)
        writer.writeheader()
        writer.writerows(json_data)

        # Return CSV content as a string
        return sio.getvalue()

    return None

def fetch_rollover_data_for_symbol(symbol) -> Optional[str]:
    """Fetch and cache rollover calendar data for a symbol.

    This function retrieves monthly rollover adjustment data for the given
    symbol from the Dukascopy service. Results are cached locally to avoid
    repeated network requests. If a valid cached file exists, it is returned
    immediately. On network failure, a stale cache may be used as a fallback.

    Args:
        symbol (str): Symbol identifier used to request rollover data.

    Returns:
        Optional[str]: Path to the cached rollover CSV file if available,
        otherwise None if no data could be retrieved.

    Note: Mixed feelings
    """

    # Build the expected cache path for the symbol
    cache_path = Path(f"{CACHE_PATH}/{symbol}.csv")

    # Return cached data if it exists and is still fresh
    if (
        cache_path.exists()
        and (cache_path.stat().st_mtime + CACHE_MAX_AGE) > int(time.time())
    ):
        return cache_path

    # Dukascopy base endpoint for rollover adjustment data
    url = "https://freeserv.dukascopy.com/2.0/"
    try:
        # Perform HTTP request to fetch rollover calendar data
        response = requests.Session().get(
            url,
            headers={
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "accept-encoding": "gzip, deflate",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/143.0.0.0 Safari/537.36"
                ),
                "referer": (
                    "https://freeserv.dukascopy.com/2.0/"
                    "?path=cfd_monthly_adjustment/index&header=false"
                    "&tableBorderColor=%23D92626&highlightColor=%23FFFAFA"
                    "&currency=USD&amount=1&width=100%25&height=500"
                    "&adv=popup&lang=en"
                ),
                "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "script",
                "sec-fetch-mode": "no-cors",
                "sec-fetch-site": "same-origin",
            },
            params={
                "path": "cfd_monthly_adjustment/getData",
                "start": "0000000000000",
                "end": "2006745599999",
                "jp": "0",
                "jsonp": "_callbacks____qmjn9av6ydd",
            },
            timeout=10,
        )
        response.raise_for_status()

        # Normalize the raw response into a CSV-compatible format
        normalized_data = normalize_data(response.text, symbol)

        # Abort if the response did not yield usable data
        if not normalized_data:
            return None

        # Persist normalized data to the local cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f_cache:
            f_cache.write(normalized_data)

        # Return path to the cached file for downstream consumption
        return cache_path

    except requests.exceptions.RequestException:
        # Fallback to stale cache if network refresh fails
        if cache_path.exists():
            print("Warning: Refresh of symbol rollover calendar failed. Using old version.")
            return cache_path
        raise

    return None


def adjust_symbol(symbol, input_filepath, output_filepath):
    """Apply Panama adjustment to a symbol's time series data.

    This function adjusts historical price data to account for contract
    rollovers using a rollover calendar. Adjustment offsets are calculated
    from rollover differences and applied cumulatively to OHLC prices,
    producing a continuous, back-adjusted time series.

    Args:
        symbol (str): Symbol identifier (e.g., futures contract root).
        input_filepath (str): Path to the raw input CSV file containing
            time-series OHLCV data.
        output_filepath (str): Path where the adjusted CSV file will be written.

    Returns:
        bool: True if the adjustment completed successfully, False if the
        rollover calendar could not be found or processing was skipped.
    """

    # Locate the rollover calendar for the given symbol
    rollover_filepath = fetch_rollover_data_for_symbol(symbol)

    # Abort if no rollover data is available
    if not rollover_filepath:
        print(
            f"Warning: Couldn't find a rollover calendar for {symbol}. "
            "Skipping Panama-adjustment."
        )
        return False

    # Informational log indicating adjustment is being applied
    print(f"Warning: Panama modifier set for {symbol}. Handling rollover gaps...")

    # SQL pipeline to compute cumulative rollover adjustments and apply them
    adjust_sql = f"""
        CREATE OR REPLACE TABLE adjustments AS
        WITH roll_diffs AS (
            SELECT 
                (strptime(date, '%d-%b-%y')::DATE
                 + INTERVAL '23 hours 59 minutes 59 seconds')::TIMESTAMP
                    AS roll_date,
                (long::DOUBLE) * -1 AS adj_value 
            FROM read_csv('{rollover_filepath}', header=True)
        ),
        cumulative AS (
            SELECT 
                roll_date,
                SUM(adj_value) OVER (ORDER BY roll_date DESC) AS total_offset
            FROM roll_diffs
        )
        SELECT * FROM cumulative;

        COPY (
            WITH raw_data AS (
                SELECT 
                    strptime(CAST(time AS VARCHAR), '{CSV_TIMESTAMP_FORMAT}') AS ts,
                    open::DOUBLE AS o,
                    high::DOUBLE AS h,
                    low::DOUBLE AS l,
                    close::DOUBLE AS c,
                    volume::DOUBLE AS v
                FROM read_csv('{input_filepath}', header=True)
            )
            SELECT 
                strftime(raw_data.ts, '{CSV_TIMESTAMP_FORMAT}') AS time,
                round(o + COALESCE(adj.total_offset, 0), 6) AS open,
                round(h + COALESCE(adj.total_offset, 0), 6) AS high,
                round(l + COALESCE(adj.total_offset, 0), 6) AS low,
                round(c + COALESCE(adj.total_offset, 0), 6) AS close,
                v AS volume
            FROM raw_data
            ASOF LEFT JOIN adjustments adj
                ON raw_data.ts <= adj.roll_date
            ORDER BY raw_data.ts ASC
        ) TO '{output_filepath}' (HEADER True, DELIMITER ',');
    """

    # Execute the adjustment logic in an in-memory DuckDB instance
    con = duckdb.connect(database=":memory:")
    con.execute(adjust_sql)
    con.close()

    return True



def fork_panama(
    task: Tuple[str, str, str, str, str, str, Dict[str, Any], Any]
) -> Tuple[str, str, str, str, str, str, Dict[str, Any]]:
    """Prepare a task for Panama-adjusted data processing if requested.

    This function inspects a task tuple and, when the `"panama"` modifier is
    present, prepares adjusted (Panama) data for the symbol. It ensures that
    adjusted base data exists, performs resampling if needed, and updates the
    task input path to point to the adjusted timeframe file. If the modifier
    is not present, the task is returned unchanged.

    Args:
        task: A tuple containing:
            symbol (str): Symbol identifier.
            timeframe (str): Target timeframe (e.g., "1m", "5m", "1h").
            input_filepath (str): Path to the input data file.
            after_str (str): Start time constraint.
            until_str (str): End time constraint.
            modifiers (str): Modifier flags (e.g., includes "panama").
            options (Dict[str, Any]): Additional processing options.

    Returns:
        A task tuple with the same structure as the input. When Panama
        adjustment is applied, the input file path is updated to reference
        the adjusted data.
    """

    # Unpack the task tuple
    symbol, timeframe, input_filepath, after_str, until_str, modifiers, options = task

    # Only apply logic when the Panama modifier is present
    if "panama" in modifiers:
        from filelock import FileLock, Timeout
        from etl.config.app_config import (
            load_app_config,
            resample_get_symbol_config,
            ResampleConfig,
        )
        from etl.resample import fork_resample

        # Load application config and symbol-specific resample configuration
        config = resample_get_symbol_config(
            symbol,
            app_config := load_app_config(options["config_file"]),
        )

        # Define all relevant paths used during Panama adjustment
        raw_base_path, adjusted_base_path, lock_path, tf_path = [
            Path(config.timeframes.get("1m").source) / f"{symbol}.csv",
            Path(options.get("output_dir")).parent / f"adjust/1m/{symbol}.csv",
            Path(options.get("output_dir")).parent / f"locks/{symbol}.lck",
            Path(options.get("output_dir")).parent / f"adjust/{timeframe}/{symbol}.csv",
        ]

        # Ensure required directories exist
        adjusted_base_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # In dry-run mode, skip all processing and return an updated task
        if options.get("dry_run"):
            print(f"DRY-RUN: Would have performed Panama adjustment for {symbol}...")
            input_filepath = tf_path
            return (
                symbol,
                timeframe,
                input_filepath,
                after_str,
                until_str,
                modifiers,
                options,
            )

        # Acquire an exclusive lock to avoid parallel adjustment for the same symbol
        lock = FileLock(lock_path)
        try:
            lock.acquire(timeout=300)
        except Timeout:
            print(
                f"Something is wrong. We couldnt acquire a lockfile {lock_path}. Exiting."
            )
            sys.exit(1)

        # If adjusted base data does not yet exist, generate it and resample
        if not adjusted_base_path.exists():
            # Generate adjusted 1m base data
            if not adjust_symbol(symbol, raw_base_path, adjusted_base_path):
                return task

            # Update app config to use adjusted base data for resampling
            app_config.resample.timeframes.get("1m").source = str(
                adjusted_base_path.parent
            )
            app_config.resample.paths.data = str(tf_path.parent.parent)

            # Perform resampling using the adjusted base data
            print(f"Warning: Panama modifier set for {symbol}. Resampling...")
            fork_resample([symbol, app_config])

        # Update input path to the adjusted timeframe file
        input_filepath = tf_path

        # Release the file lock
        lock.release()

        # Rebuild the task tuple with the updated input path
        task = (
            symbol,
            timeframe,
            input_filepath,
            after_str,
            until_str,
            modifiers,
            options,
        )

    return task
