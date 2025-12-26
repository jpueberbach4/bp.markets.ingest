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
import sys
from pathlib import Path

from typing import Tuple, Dict, Any

# Since we (potentially) import from ETL folder, we need to app a syspath
sys.path.append(str(Path(__file__).resolve().parent.parent))

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

    symbol, timeframe, input_filepath, after_str, until_str, modifiers, options = task

    # Determine output configuration
    output_type = options.get("output_type", "parquet").upper()
    compression = options.get("compression", "zstd").upper()
    is_partitioned = options.get("partition", False)

    # Dry-run mode: print what would be done
    if options.get("dry_run"):
        print(
            f"DRY-RUN: {symbol}/{timeframe} => {input_filepath} "
            f"(mode: {output_type}, modifiers: {modifiers})"
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
        where_clause += (
            f" AND {time_column} < ("
            f"SELECT MAX({time_column}) "
            f"FROM read_csv_auto('{input_filepath}')"
            f")"
        )

    # Build DuckDB read CSV statement
    read_csv_sql = f"""
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
            FROM ({read_csv_sql})
            {where_clause}
        )
        TO '{output_path}'
        (
            {format_options}
        );
    """

    # Execute COPY in an isolated in-memory DuckDB instance
    con = duckdb.connect(database=":memory:")
    con.execute(copy_sql)
    con.close()

    return True


def prepare_symbol(
    task: Tuple[str, str, str, str, str, str, Dict[str, Any], Any]
) -> Tuple[str, str, str, str, str, str, Dict[str, Any]]:
    """Prepare a symbol task for processing, optionally handling adjusted data.

    This function unpacks a task tuple describing a symbol processing job.
    If the task includes the `"adjusted"` modifier, the function is intended
    to prepare adjusted timeframe data by generating or reusing temporary
    adjusted files and updating task paths accordingly. If no adjustment is
    required, the task is returned unchanged.

    Args:
        task: A tuple containing:
            - symbol (str): Symbol identifier (e.g., ticker or instrument name).
            - timeframe (str): Target timeframe (e.g., "1m", "5m", "1h").
            - input_filepath (str): Path to the input data file.
            - after_str (str): Start time constraint as a string.
            - until_str (str): End time constraint as a string.
            - modifiers (str): Modifier flags (e.g., includes "adjusted").
            - options (Dict[str, Any]): Additional processing options.

    Returns:
        A task tuple with the same structure as the input. If adjustment logic
        is applied, the returned tuple may contain modified file paths and/or
        options reflecting the adjusted data preparation.
    """

    symbol, timeframe, input_filepath, after_str, until_str, modifiers, options = task

    if "adjusted" in modifiers:

        from filelock import FileLock, Timeout
        from etl.config.app_config import load_app_config, resample_get_symbol_config
        # get symbol configuration
        config = resample_get_symbol_config(
            symbol,
            app_config := load_app_config('config.user.yaml') 
        )
        # 1m source path, first version just gets from root, nobody overrides 1m frame
        raw_base_path, adjusted_base_path, lock_path, tf_path = [
            Path(config.timeframes.get("1m").source) / f"{symbol}.csv",
            Path(options.get('output_dir')) / f"adjust/1m/{symbol}.csv",
            Path(options.get('output_dir')) / f"locks/{symbol}.lck",
            Path(options.get('output_dir')) / f"adjust/{timeframe}/{symbol}.csv",
        ]
        # Create directories
        adjusted_base_path.parent.mkdir(parents=True,exist_ok=True)
        lock_path.parent.mkdir(parents=True,exist_ok=True)

        # Acquire exclusive filelock, no simultaneous adjustment logic for same symbol
        lock = FileLock(lock_path)
        try:
            lock.acquire(timeout=300)
            # We acquired the lock, continue
        except Timeout:
            sys.exit(1)    
        
        # Check if we already have an adjusted file for this tf (adjust/tf/symbol.csv)
        if not adjusted_base_path.exists():
            # It was not already prepared in an other parallel process

            # Now, prepare the adjusted 1m file and account for the rollover gaps, CALL adjust.adjust_symbol
            # Adjust the 1m base timeframe source PATH(!), recursively in app_config (for symbol)

            # Now, adjust resample.paths.data in app_config, set to tempdir/adjust (tf's directly below)
            app_config.resample.paths.data = tf_path.parent.parent
            # CALL the fork_resample(symbol, app_config)
            # It will start resampling
            # Todo: exception handling and such
        
        # We are done here, now set input_filepath to tf_path
        input_filepath = tf_path

        # And release the lock...
        lock.release()

        # Return the adjusted task
        task = (symbol, timeframe, input_filepath, after_str, until_str, modifiers, options)

    return task

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
    # Prepares a symbol when certain modifiers are set
    task = prepare_symbol(task)

    # Now executes the regular extraction
    return extract_symbol(task)
