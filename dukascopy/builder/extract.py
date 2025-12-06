#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
File:        extract.py
Author:      JP Ueberbach
Created:     2025-12-06
Description: Extract to parquet

This module provides functionality to extract, filter, transform, and export
financial time series data from Dukascopy CSV files into partitioned Parquet 
datasets using DuckDB. 

It supports:
- Reading CSV files with a predefined Dukascopy schema.
- Filtering data by a date range.
- Optional exclusion of the most recent open candle.
- Exporting data into Parquet format partitioned by symbol and year.
- Customizable compression format for Parquet output.
- Integration with multiprocessing workflows.

Functions:
- extract_symbol(task: Tuple[str, str, str, str, str, Dict[str, Any]]) -> bool
    Processes a single CSV file and writes the resulting data to Parquet.
- fork_extract(task: Tuple[str, str, str, str, str, Dict[str, Any]]) -> bool
    Wrapper for multiprocessing pool execution of `extract_symbol`.

Dependencies:
- duckdb
- pathlib
- datetime
- uuid
- typing
- os
"""

import duckdb
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, Any

# Define the expected schema for Dukascopy data
DUKASCOPY_CSV_SCHEMA = {
    'Time': 'TIMESTAMP',
    'Open': 'DOUBLE',
    'High': 'DOUBLE',
    'Low': 'DOUBLE',
    'Close': 'DOUBLE',
    'Volume': 'DOUBLE',
}

CSV_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'

def extract_symbol(task: Tuple[str, str, str, str, str, Dict[str, Any]]) -> bool:
    """
    Extracts, filters, transforms, and exports a single CSV file to a 
    partitioned Parquet dataset using a single DuckDB COPY statement.

    Args:
        task: Tuple containing (symbol, timeframe, filepath, after_str, until_str, options_dict).
              Note: 'after' and 'until' are passed as strings to be process-safe.
              
    Returns:
        bool: True on successful execution. Raises Exception on failure.
    """
    symbol, timeframe, input_filepath, after_str, until_str, options = task

    if options['dry_run']:
        print(f"DRY-RUN: {symbol}/{timeframe} => {input_filepath}")
        return False

    
    root_output_dir = options.get('output_dir', './temp/parquet')

    if not Path(root_output_dir).exists():
        Path(root_output_dir).parent.mkdir(parents=True, exist_ok=True)
        
    select_columns = f"""
        '{symbol}'::VARCHAR AS symbol,
        '{timeframe}'::VARCHAR AS timeframe,
        CAST(strftime(Time, '%Y') AS VARCHAR) AS year,
        strptime(CAST(Time AS VARCHAR), '{CSV_TIMESTAMP_FORMAT}') AS Time,
        Open,
        High,
        Low,
        Close,
        Volume
    """
    
    time_column_name = list(DUKASCOPY_CSV_SCHEMA.keys())[0]

    where_clause = f"""
        WHERE {time_column_name} >= TIMESTAMP '{after_str}'
          AND {time_column_name} < TIMESTAMP '{until_str}'
    """
    
    if options.get('omit_open_candles') and not timeframe == "1m" :
        # BUG: also omits last 1m candle but that one is (always) completed
        where_clause += f" AND {time_column_name} < (SELECT MAX({time_column_name}) FROM read_csv_auto('{input_filepath}'))"
    
    read_csv_sql = f"""
        SELECT *
        FROM read_csv_auto(
            '{input_filepath}',
            columns={DUKASCOPY_CSV_SCHEMA}
        )
    """

    copy_sql = f"""
        COPY (
            SELECT {select_columns}
            FROM ({read_csv_sql})
            {where_clause}
        )
        TO '{root_output_dir}' 
        (
            FORMAT PARQUET,
            PARTITION_BY (symbol, year),
            FILENAME_PATTERN 'part_{{uuid}}',
            COMPRESSION '{options.get('compression', 'zstd').upper()}',
            OVERWRITE_OR_IGNORE
        );
    """

    con = duckdb.connect(database=':memory:')
    con.execute(copy_sql)
    con.close()
    
    return True

# --- Wrapper for multiprocessing (required by run.py) ---
def fork_extract(task: Tuple[str, str, str, str, str, Dict[str, Any]]) -> bool:
    """Wrapper function for multiprocessing pool."""
    return extract_symbol(task)
