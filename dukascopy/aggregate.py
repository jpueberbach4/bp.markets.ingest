#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        aggregate.py
 Author:      JP Ueberbach
 Created:     2025-11-09
 Description: Incrementally loads symbol CSV files into a single aggregated file.
              Supports resumable loading and parallel processing.

 Usage:
     python3 aggregate.py

 Requirements:
     - Python 3.8+
     - Pandas
     - filelock
     - tqdm

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

START_DATE = "2025-11-01"               # Start date for historic data loading
NUM_PROCESSES = os.cpu_count()          # Number of simultaneous loaders
DELETE_AGGREGATES = False
DELETE_INDEX = False

INDEX_PATH = "data/aggregate/1m/index"  # Use offset-pointers from this location
DATA_PATH = "data/transform/1m"         # Data of aggregate.py is stored here
TEMP_PATH = "temp"                      # Today's live data is stored here
AGGREGATE_PATH = "data/aggregate/1m"    # Output path for the aggregated files

def init_process(symbols):
    """
    Initialize environment before loading symbols.

    Deletes existing aggregated CSV files or index files
    if the corresponding flags (DELETE_AGGREGATES, DELETE_INDEX) are set.

    Parameters
    ----------
    symbols : list[str]
        List of trading symbols to initialize.
    """
    if DELETE_AGGREGATES:
        for symbol in symbols:
            Path(f"{AGGREGATE_PATH}/{symbol}.csv").unlink(missing_ok=True)

    if DELETE_INDEX:
        for path in ["index", "temp"]:
            for file in Path(path).rglob("*.idx"):
                file.unlink(missing_ok=True)


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


def aggregate_symbol(symbol: str, dt: date) -> bool:
    """
    Load incremental data for a single symbol and date.

    Checks both 'data' and 'temp' directories for CSV and index files,
    resumes from the last processed position (tracked in the index file),
    and appends new data to the aggregated CSV in 'load/'.

    Parameters
    ----------
    symbol : str
        Trading symbol to load.
    dt : date
        Specific date of the data to load.

    Returns
    -------
    bool
        True if new data was successfully loaded; False if files are missing
        or no new data is available.
    """
    try:
        acquire_lock(symbol, dt)

        # --- Source paths ---
        data_path = Path(DATA_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.csv")
        index_path = Path(INDEX_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.idx")

        index_path.parent.mkdir(parents=True, exist_ok=True)

        if data_path.is_file():
            # We will use the historic data path
            index_temp_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.idx")

            if index_temp_path.is_file():
                os.replace(index_temp_path, index_path)
        else:
            # We will use the temp path as source
            data_path = Path(TEMP_PATH) / f"{symbol}_{dt:%Y%m%d}.csv"
            index_path = Path(TEMP_PATH) / f"{symbol}_{dt:%Y%m%d}.idx"

        if not data_path.is_file():
            return False

        # --- Resume processing from last position ---
        position = 0

        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                position = int(f.read().strip())

        if position >= data_path.stat().st_size:
            return False

        # --- Destination paths ---
        aggregate_path = Path(f"{AGGREGATE_PATH}/{symbol}.csv")
        aggregate_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = aggregate_path.with_suffix(".tmp")

        try:
            header = None
            with open(data_path, "r", encoding="utf-8") as f_in, \
                 open(temp_path, "w", encoding="utf-8") as f_out:

                if position == 0:
                    header = f_in.readline()  # skip header
                else:
                    f_in.seek(position)

                while line := f_in.readline():
                    line = line.strip()
                    if line:
                        f_out.write(f"{line}\n")

                    # Update resume index
                    position = f_in.tell()
            
            # if aggregate_path exists, do not write header
            if aggregate_path.exists():
                header = None

            # Atomic append to aggregate CSV
            with open(aggregate_path, "a", encoding="utf-8") as f_out, \
                    open(temp_path, "r", encoding="utf-8") as f_in, \
                        open(index_path, "w+", encoding="utf-8") as f_idx:
                    """
                    BUG-002: When f_out write is interrupted (SIGTERM, OOM, ...), the idx file may not get written and/or aggregate file 
                    may get partially updated, leading to invalid data in aggregate file. Solution is to have and idx file acting as 
                    a "single source of truth" containing both the input pointer as well as the aggregate pointer. Store aggregate pointer 
                    before write to the idx file. Always truncate to this pointer before writing. Keep track of new pointers in tmp idx 
                    file and os replace tmp to idx file at the end (atomic operation).
                    """
                    if header:
                        f_out.write(header)

                    f_out.write(f_in.read())
                    f_idx.seek(0)
                    f_idx.write(str(position))
                    f_idx.truncate()
                    f_idx.flush()

            temp_path.unlink(missing_ok=True)
            return True

        except Exception as e:
            tqdm.write(f"Load failed {symbol} {dt}: {e}")
            temp_path.unlink(missing_ok=True)
            return False

    except KeyboardInterrupt:
        tqdm.write(f"Interrupted by user")
        return False
    finally:
        release_lock(symbol, dt)
    
    return True


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
    init_process(symbols)

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
