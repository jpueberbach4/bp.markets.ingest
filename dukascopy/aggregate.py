#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        aggregate.py
 Author:      JP Ueberbach
 Created:     2025-11-09
 Description: Incrementally aggregates daily trading symbol CSV files into
              a single per-symbol CSV file. Supports:
              
              - Resumable aggregation via atomic index files
              - Crash-safe incremental writes
              - Parallel processing across multiple symbols
              - Day-level CSV input (small files, fully controlled input)
              
              This script is designed for high reliability and reproducibility,
              with no memory concerns due to small per-day files.

 Usage:
     python3 aggregate.py

 Requirements:
     - Python 3.8+
     - Pandas
     - tqdm

 Notes:
     - Input CSVs must follow the pattern: DATA_PATH/YYYY/MM/{symbol}_YYYYMMDD.csv
     - Aggregated output CSVs are stored in: AGGREGATE_PATH/{symbol}.csv
     - Incremental progress is tracked in AGGREGATE_PATH/index/{symbol}.idx
     - Supports safe recovery from crashes or interruptions
     - Parallelism is controlled by NUM_PROCESSES (default: os.cpu_count())

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import os
from datetime import date, datetime
from pathlib import Path
from typing import Tuple

START_DATE = "2025-11-01"               # Start date for historic data loading
NUM_PROCESSES = os.cpu_count()          # Number of simultaneous loaders

INDEX_PATH = "data/aggregate/1m/index"  # Use offset-pointers from this location
DATA_PATH = "data/transform/1m"         # Data of aggregate.py is stored here
TEMP_PATH = "data/temp"                 # Data of today
AGGREGATE_PATH = "data/aggregate/1m"    # Output path for the aggregated files

def load_symbols() -> pd.Series:
    """
    Load and normalize the list of trading symbols.

    Reads symbols from 'symbols.txt', converts them to strings,
    and replaces '/' with '-' for uniformity.

    Returns
    -------
    pd.Series
        Series of normalized trading symbols.
    """
    df = None
    if Path("symbols.user.txt").exists():
        df = pd.read_csv('symbols.user.txt')
    else:
        df = pd.read_csv('symbols.txt')
    return df.iloc[:, 0].astype(str).str.replace('/', '-', regex=False)


def aggregate_read_index(index_path: Path) -> Tuple[date, int, int]:
    """
    Read the incremental resampling index file and return the stored offsets.

    Parameters
    ----------
    index_path : Path
        Path to the `.idx` file storing the aggregator's progress for a single
        symbol. The file contains exactly three lines:
            1) date – a string in format YYYY-MM-DD
            1) input_position  – byte offset in the upstream CSV already processed
            2) output_position – byte offset in the output CSV already written

    Returns
    -------
    Tuple[date,int, int]
        (date, input_position, output_position), positions both guaranteed to be integers.

    Notes
    -----
    These offsets allow the resampling engine to:
        - Resume exactly where it left off after a crash or restart.
        - Avoid re-reading previously processed input data.
        - Avoid rewriting historical output candles.
    The index file is always written atomically elsewhere in the pipeline to
    ensure it is safe against partial writes or corruption.
    """
    if not index_path.exists():
        aggregate_write_index(index_path, datetime.utcfromtimestamp(0).date(), 0, 0)
        return datetime.utcfromtimestamp(0).date(),0, 0
    
    with open(index_path, 'r') as f_idx:
        lines = f_idx.readlines()[:3]
        if len(lines) != 3:
            raise
        date_str, input_position, output_position = [
            line.strip() for line in lines
        ]
    return datetime.strptime(date_str, "%Y-%m-%d").date(),int(input_position), int(output_position)

def aggregate_write_index(index_path: Path, dt: date, input_position: int, output_position: int) -> bool:
    """
    Write an atomic aggregate index file for crash-safe ETL processing.

    This function writes the index file containing the input date, the last
    read position in the input (transformed) file, and the last written 
    position in the aggregate output file. It uses a temporary file and
    atomic replace to ensure the index file is never partially written.

    Parameters
    ----------
    index_path : Path
        Full path to the target index file.
    dt : date
        The date corresponding to the input CSV file being aggregated.
    input_position : int
        Byte offset or line number indicating how far the input file has
        been processed.
    output_position : int
        Byte offset indicating how far the aggregate file has been written.

    Returns
    -------
    bool
        True if the index file was successfully written and replaced.

    Notes
    -----
    - The index file format is three lines:
        1. date in YYYY-MM-DD format
        2. input position
        3. output position
    - This function ensures atomic writes by writing to a temporary file first
      and then replacing the original file using os.replace().
    - Parent directories will be created if they do not exist.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_temp_path = Path(f"{index_path}.tmp")
    with open(index_temp_path, "w") as f_idx:
        date_str = dt.strftime("%Y-%m-%d")
        f_idx.write(f"{date_str}\n{input_position}\n{output_position}")
        f_idx.flush()

    os.replace(index_temp_path, index_path)
    return True

def aggregate_symbol(symbol: str, dt: date) -> bool:
    """
    Incrementally load and aggregate CSV data for a single trading symbol and date.

    This function appends new rows from a per-day transformed CSV into the
    aggregated CSV for the symbol, using an index file to track progress.
    It ensures crash-safe incremental updates by:

    - Resuming from the last processed position stored in the index file.
    - Truncating the aggregate CSV if it was partially written.
    - Updating the index file atomically after successful writes.

    Parameters
    ----------
    symbol : str
        Trading symbol to process (e.g., "EURUSD").
    dt : date
        The specific date of the source CSV to aggregate.

    Returns
    -------
    bool
        True if new data was successfully appended to the aggregate CSV.
        False if:
        - No new data is available,
        - The input CSV files are missing,
        - Or the current date is earlier than the last processed date.

    Notes
    -----
    - The input CSV is expected to be located in `DATA_PATH/YYYY/MM/{symbol}_YYYYMMDD.csv`.
    - The aggregated CSV is stored in `AGGREGATE_PATH/{symbol}.csv`.
    - The index file format is three lines: 
        1. date (YYYY-MM-DD)
        2. input_position (byte offset in input CSV)
        3. output_position (byte offset in aggregate CSV)
    - The function uses `aggregate_write_index` for atomic index updates.
    - Any partial writes or crashes can be safely recovered by rerunning this function.
    """
    # Construct paths
    index_path = Path(AGGREGATE_PATH) / f"index/{symbol}.idx"
    output_path = Path(AGGREGATE_PATH) / f"{symbol}.csv"
    input_path = Path(DATA_PATH) / f"{dt.year}/{dt.month:02}/{symbol}_{dt:%Y%m%d}.csv"

    if not input_path.exists():
        # Assume we should look in data/temp
        input_path =  Path(TEMP_PATH) / f"{symbol}_{dt:%Y%m%d}.csv"
        if not input_path.exists():
            return False
    
    # Read index file
    date_from, input_position, output_position = aggregate_read_index(index_path)

    # Skip if this date is already fully processed
    if dt < date_from:
        return False

    # Reset input offset if processing a new date
    if dt > date_from:
        input_position = 0

    # Ensure output file exists
    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w"):
            pass

    # Open files for random access
    with open(output_path, "r+", encoding="utf-8") as f_output, \
            open(input_path, "r", encoding="utf-8") as f_input:

            # Always read header
            header = f_input.readline()

            if input_position > 0:
                # We have partly read this file before, advance pointer
                f_input.seek(input_position)

            # Crash rewind
            f_output.truncate(output_position)

            # Start writing from here
            f_output.seek(output_position)

            # Output file new, write header
            if output_position == 0:
                f_output.write(header)
            
            # Read data until we hit EOF
            data = f_input.read()

            if not data:
                # EOF without data
                return False

            # Append to output
            f_output.write(data)

            # Flush
            f_output.flush()
            
            # Update pointers
            input_position = f_input.tell()
            output_position = f_output.tell()

            # Write index file
            aggregate_write_index(index_path, dt, input_position, output_position)

    return True
  


def fork_aggregate(args) -> bool:
    """
    Process all dates for a single symbol sequentially.

    Intended for use with multiprocessing where each worker handles
    one symbol over the full date range.

    Parameters
    ----------
    args : tuple
        A tuple of the form (symbol, dates), where:
        - symbol : str
            The symbol to aggregate.
        - dates : list[datetime.date]
            The list of trading dates to process sequentially.

    Returns
    -------
    bool
        True if all dates were processed successfully,
        False if interrupted by the user.
    """
    symbol, dates = args
    try:
        for dt in dates:
            aggregate_symbol(symbol, dt)
    except Exception as e:
        raise
    finally:
        pass
    
    return True
