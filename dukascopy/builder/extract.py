#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        extract.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Module for extracting, filtering, and exporting Dukascopy CSV 
              datasets to Parquet or CSV formats using DuckDB.

              Provides:
              - extract_symbol: process a single (symbol, timeframe) CSV file.
              - fork_extract: wrapper for multiprocessing pool execution.

              Features:
              - Time range filtering
              - Optional exclusion of the latest row via modifier
              - Metadata injection (symbol, timeframe, year)
              - Partitioned or single-file output
              - Supports dry-run mode for debugging

 Requirements:
     - Python 3.8+
     - duckdb

 License:
     MIT License
===============================================================================
"""
import duckdb
import uuid
import mmap
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any

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

# Define the C-struct equivalent for numpy
DTYPE = np.dtype([
    ('ts', '<u8'),           # Timestamp in milliseconds
    ('ohlcv', '<f8', (5,)),  # Open, High, Low, Close, Volume
    ('padding', '<u8', (2,)) # Padding to 64 bytes
])

RECORD_SIZE = 64  # Fixed size of each record in bytes.
                    # Aligned to standard x86_64 CPU cache-line size.
                    # This ensures a single record never spans across two cache lines,
                    # minimizing memory latency and preventing split-load penalties.


def extract_symbol(task: Tuple[str, str, str, str, str, str, Dict[str, Any]]) -> bool:
    """
    Extract and export a single Dukascopy CSV file to Parquet or CSV.

    Parameters:
    -----------
    task : tuple
        (symbol, timeframe, input_filepath, after_str, until_str, modifier, options)
        - symbol: Asset symbol (e.g., 'EURUSD')
        - timeframe: Bar interval (e.g., '1m')
        - input_filepath: Path to source CSV file
        - after_str: Start time (inclusive)
        - until_str: End time (exclusive)
        - modifier: Optional modifier (e.g., 'skiplast')
        - options: Dictionary of export options including output_type, partition,
                   compression, output_dir, dry_run

    Returns:
    --------
    bool
        True if extraction executed successfully, False if dry-run.
    """

    symbol, timeframe, input_filepath, after_str, until_str, modifiers, indicators, options = task

    # Determine output configuration
    output_type = options.get("output_type", "parquet").upper()
    compression = options.get("compression", "zstd").upper()
    is_partitioned = options.get("partition", False)

    # Dry-run mode: print what would be done
    if options.get("dry_run"):
        print(
            f"DRY-RUN: {symbol}/{timeframe} => {input_filepath} "
            f"(mode: {output_type}, modifier: {modifiers})"
        )
        return False

    # Ensure output directory exists
    root_output_dir = options.get("output_dir", f"./data/temp/{output_type.lower()}")
    Path(root_output_dir).mkdir(parents=True, exist_ok=True)

    # Configure output paths and COPY format options
    if output_type == "PARQUET":
        output_path = root_output_dir
        format_options = f"""
            FORMAT PARQUET,
            PARTITION_BY (symbol, year),
            FILENAME_PATTERN 'part_{{uuid}}',
            COMPRESSION '{compression}',
            OVERWRITE_OR_IGNORE
        """
    elif output_type == "CSV":
        if is_partitioned:
            output_path = root_output_dir
            format_options = f"""
                FORMAT CSV,
                PARTITION_BY (symbol, year),
                FILENAME_PATTERN 'part_{{uuid}}',
                COMPRESSION '{compression}',
                HEADER true,
                DELIMITER ',',
                OVERWRITE_OR_IGNORE
            """
        else:
            output_path = Path(root_output_dir) / f"{symbol}_{timeframe}_{uuid.uuid4()}.csv"
            format_options = f"""
                FORMAT CSV,
                COMPRESSION '{compression}',
                HEADER true,
                DELIMITER ',',
                OVERWRITE_OR_IGNORE
            """
    else:
        raise ValueError(f"Unsupported output type: {output_type}")

    # Build SELECT columns with injected metadata
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

    # Base time column for filtering
    time_column = next(iter(DUKASCOPY_CSV_SCHEMA))

    # Apply time window filter
    where_clause = f"""
        WHERE {time_column} >= TIMESTAMP '{after_str}'
          AND {time_column} < TIMESTAMP '{until_str}'
    """

    # Optional modifier: skip the latest timestamp
    if "skiplast" in modifiers:
        if options.get("fmode") == "binary":
            where_clause += (
                f" AND {time_column} < ("
                f"SELECT MAX(epoch_ms(time_raw::BIGINT)) "
                f"FROM ohlcv_view"
                f")"
            )
        else:
            where_clause += (
                f" AND {time_column} < ("
                f"SELECT MAX({time_column}) "
                f"FROM read_csv_auto('{input_filepath}')"
                f")"
            )

    if options.get("fmode") == "binary":
        read_sql = f"""
            SELECT epoch_ms(time_raw::BIGINT) AS time, 
            open, high, low, close, volume FROM ohlcv_view
        """
    else:

        # Build DuckDB read CSV statement
        read_sql = f"""
            SELECT *
                FROM read_csv_auto(
                    '{input_filepath}',
                    columns={DUKASCOPY_CSV_SCHEMA}
                )
        """

    # Build final COPY statement
    copy_sql = f"""
        COPY (
            SELECT {select_columns}
            FROM ({read_sql})
            {where_clause}
        )
        TO '{output_path}'
        (
            {format_options}
        );
    """

    # Execute COPY in an isolated in-memory DuckDB instance
    con = duckdb.connect(database=":memory:")

    if options.get("fmode") == "binary":
        # We are in binary mode, open file as binary
        f = open(input_filepath,"rb")
        # Memory map the file
        mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        # Create a zero copy view
        data_view = np.frombuffer(mm, dtype=DTYPE)
        # map the view to a data dict
        data_dict = {
            "time_raw": data_view['ts'],
            "open": data_view['ohlcv'][:, 0],
            "high": data_view['ohlcv'][:, 1],
            "low": data_view['ohlcv'][:, 2],
            "close": data_view['ohlcv'][:, 3],
            "volume": data_view['ohlcv'][:, 4]
        }

        # Register view in duckdb
        con.register('ohlcv_view', pd.DataFrame(data_dict))
        con.execute(copy_sql)
        con.unregister('ohlcv_view')
        con.close()
        del data_dict
        del data_view
        mm.close()
        f.close()
        return True

    con.execute(copy_sql)
    con.close()

    return True


def fork_extract(task: Tuple[str, str, str, str, str, str, Dict[str, Any]]) -> bool:
    """
    Wrapper function for multiprocessing pool execution of extract_symbol.

    Parameters:
    -----------
    task : tuple
        Same as extract_symbol.

    Returns:
    --------
    bool
        Result of extract_symbol.
    """
    try:

        from panama.adjust import fork_panama
        task = fork_panama(task)
        return extract_symbol(task)
    except Exception as e:
        import traceback
        traceback.print_exc()

