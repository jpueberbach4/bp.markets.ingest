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
     - filelock
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
from utils.locks import acquire_lock, release_lock
from tqdm import tqdm
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from multiprocessing import get_context
from typing import Tuple

START_DATE = "2025-11-01"               # Start date for historic data loading
NUM_PROCESSES = os.cpu_count()          # Number of simultaneous loaders

INDEX_PATH = "data/aggregate/1m/index"  # Use offset-pointers from this location
DATA_PATH = "data/transform/1m"         # Data of aggregate.py is stored here
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
        date_str, input_position, output_position = [
            line.strip() for line in f_idx.readlines()[:3]
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

    os.replace(index_temp_path, index_path)
    return True

def aggregate_symbol(symbol: str, dt: date) -> bool:
    """
    Incrementally load and aggregate CSV data for a single trading symbol and date.

    This function appends new rows from a per-day transformed CSV into the
    aggregated CSV for the symbol, using an index file to track progress.
    It ensures crash-safe incremental updates by:

    - Acquiring a per-symbol lock to prevent concurrent writes.
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
        - The input CSV or index files are missing,
        - An error occurs during read/write,
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
    - Per-symbol locks prevent race conditions during concurrent execution.
    """
    try:
        acquire_lock(symbol, dt)

        # Construct paths
        index_path = Path(AGGREGATE_PATH) / f"index/{symbol}.idx"
        output_path = Path(AGGREGATE_PATH) / f"{symbol}.csv"
        
        date_from, input_position, output_position = aggregate_read_index(index_path)

        # skip if current dt < resume date
        if dt < date_from:
            return False

        input_path = Path(DATA_PATH) / f"{dt.year}/{dt.month:02}/{symbol}_{dt:%Y%m%d}.csv"

        try:
                
            with open(output_path, "a", encoding="utf-8") as f_output, \
                    open(input_path, "r", encoding="utf-8") as f_input:

                    f_output.seek(output_position)
                    f_output.truncate()

                    if output_position == 0:
                        f_output.write(f_input.readline())
                    
                    if input_position > 0:
                        f_input.seek(input_position)
                    
                    # chunking not needed, input files are small
                    f_output.write(f_input.read())
                    
                    input_position = f_input.tell()
                    output_position = f_output.tell()

                    aggregate_write_index(index_path, dt, input_position, output_position)

            return True

        except Exception as e:
            tqdm.write(f"Load failed {symbol} {dt}: {e}")

    except KeyboardInterrupt:
        tqdm.write(f"Interrupted by user")
    finally:
        release_lock(symbol, dt)

    return False    


def fork_aggregate(args):
    """
    Process all dates for a single symbol sequentially.

    Intended for use with multiprocessing where each worker handles
    one symbol over the full date range.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, list of dates).
    """
    symbol, dates = args
    for dt in dates:
        aggregate_symbol(symbol, dt)


if __name__ == "__main__":
    print(f"Aggregate - Aggregates symbols to 1-minute CSV ({NUM_PROCESSES} parallelism)")
    symbols = load_symbols()

    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    today_dt = datetime.now(timezone.utc).date()
    dates = [start_dt + timedelta(days=i) for i in range((today_dt - start_dt).days + 1)]

    tasks = [(symbol, dates) for symbol in symbols]

    ctx = get_context("spawn")
    with ctx.Pool(processes=NUM_PROCESSES) as pool:
        for _ in tqdm(pool.imap_unordered(fork_aggregate, tasks, chunksize=1),
                      total=len(tasks), unit='symbols', colour='white'):
            pass

    print(f"Done. Loaded {len(tasks)} symbols.")
