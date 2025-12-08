#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        run.py
 Author:      JP Ueberbach
 Created:     2025-11-15
 Description: Runs pipeline stages in correct order

              Pipeline stages:
              1. Download HST JSON data from Dukascopy (`download.py`)
              2. Transform JSON -> OHLC CSV (`transform.py`)
              3. Aggregate daily CSVs into symbol-level CSVs (`aggregate.py`)
              4. Resample symbol-level data to higher timeframes (`resample.py`)

 Usage:
     python3 run.py

 Requirements:
     - Python 3.8+
     - filelock
     - tqdm

 License:
     MIT License
===============================================================================
"""

import os
import math
import time
import sys
import pandas as pd
from config.app_config import AppConfig, load_app_config
from filelock import FileLock, Timeout
from datetime import datetime, timezone, timedelta
from pathlib import Path
from multiprocessing import get_context
from tqdm import tqdm

# Import the existing pipeline modules
import download
import transform
import aggregate
import resample

# Start date for ETL processing in "YYYY-MM-DD"
START_DATE =  None

# Paths for cached and transformed data
CACHE_PATH = "cache"                # Cache of downloaded JSON HST files
DATA_PATH = "data/transform/1m"     # Output path for transformed OHLC CSV files
LOCK_PATH = "data/locks"                 # Where to store run.lock

# Number of worker processes for parallel stages
NUM_PROCESSES = os.cpu_count()

NOLOCK = os.getenv('NOLOCK', '0').lower() in ('1', 'true', 'yes', 'on')

# No START_DATE set, set it to 7 days back (todo: scan for last cached json date?)
if not START_DATE:
    # Check if its set in environment
    START_DATE = os.getenv('START_DATE', None)
    # If not, set back one week
    if not START_DATE:
        START_DATE = (datetime.now(timezone.utc)- timedelta(days=7)).strftime("%Y-%m-%d")

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
    
    # Deduplicate symbols to prevent race conditions during parallel processing, 
    # where multiple workers try to write/replace the same output file.
    series = df.iloc[:, 0].astype(str).str.replace('/', '-', regex=False)
    return series.unique()

def load_config() -> AppConfig:
    """
    Load the application configuration from a YAML file.

    This function checks for a user-specific configuration file first:
        - If 'config.user.yaml' exists, it is loaded.
        - Otherwise, it falls back to the default 'config.yaml'.

    Returns
    -------
    AppConfig
        A fully populated AppConfig instance containing all module configurations,
        with defaults applied where fields are missing.
    """
    if Path("config.user.yaml").exists():
        config = load_app_config('config.user.yaml')
    else:
        config = load_app_config('config.yaml')

    return config


def main():
    """
    Main entry point for running the Dukascopy ETL pipeline.

    Steps:
    1. Load symbols and generate tasks based on missing files
    2. Execute download, transform, and aggregate stages in parallel using a single pool
    3. Measure and report total runtime
    """
    start_time = time.time()  # Record wall-clock start time
    print(f"Running Dukascopy ETL pipeline ({NUM_PROCESSES} processes)")

    # run.lock
    RUN_LOCK = Path(f"{LOCK_PATH}/run.lock")

    print(f"Using lockfile {RUN_LOCK}")
    RUN_LOCK.parent.mkdir(parents=True,exist_ok=True)
    lock = FileLock(RUN_LOCK)

    try:
        if not NOLOCK:
            lock.acquire(timeout=1)
    except Timeout:
        print("Another instance is running. Exiting.")
        return

    try:
        # Load trading symbols from symbols.txt
        symbols = load_symbols()

        # Load YAML config (currently only resample support)
        config = load_config()

        # Generate list of dates to process (from START_DATE to today UTC)
        start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()
        today_dt = datetime.now(timezone.utc).date()
        dates = [start_dt + timedelta(days=i) for i in range((today_dt - start_dt).days + 1)]

        # Prepare download tasks for JSON files that are missing
        download_tasks = [
            (sym, dt, config)
            for dt in dates
            for sym in symbols
            if not Path(f"{CACHE_PATH}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.json").is_file()
        ]

        # Prepare transform tasks for CSV files that are missing
        transform_tasks = [
            (sym, dt, config)
            for dt in dates
            for sym in symbols
            if not Path(f"{DATA_PATH}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.csv").is_file()
        ]

        # Prepare aggregate tasks (one per symbol, covering all dates)
        aggregate_tasks = [(sym, dates, config) for sym in symbols]

        # Prepare resample tasks (one per symbol)
        resample_tasks = [(symbol, config) for symbol in symbols]

        # Create a single multiprocessing context to minimize process spawn overhead
        ctx = get_context("fork")
        pool = ctx.Pool(processes=NUM_PROCESSES)

        # Define pipeline stages with associated task lists and chunk sizes
        stages = [
            (
                "Download",
                download.fork_download,
                download_tasks,
                max(1, min(32, math.floor(math.sqrt(len(download_tasks)) / NUM_PROCESSES))),
                "downloads"
            ),
            (
                "Transform",
                transform.fork_transform,
                transform_tasks,
                max(1, min(128, int(math.sqrt(len(transform_tasks)) / NUM_PROCESSES) or 1)),
                "files"
            ),
            (
                "Aggregate",
                aggregate.fork_aggregate,
                aggregate_tasks,
                1,
                "symbols"
            ),
            (
                "Resample",
                resample.fork_resample,
                resample_tasks,
                1,
                "symbols"
            )
        ]

        # Run each stage in the same pool, with progress bars
        with pool:
            for name, func, tasks, chunksize, unit in stages:
                if not tasks:
                    print(f"Skipping {name} (no tasks)")
                    continue
                try:
                    print(f"Step: {name}...")
                    for _ in tqdm(pool.imap_unordered(func, tasks, chunksize=chunksize),
                            total=len(tasks), unit=unit, colour='white'):
                        pass
                except Exception as e:
                    print(f"\nABORT! Critical error in {name}.\n{type(e).__name__}: {e}")
                    break


        # Report total wall-clock runtime
        elapsed = time.time() - start_time
        print("\nETL pipeline complete!")
        print(f"Total runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
    finally:
        lock.release()


if __name__ == "__main__":
    main()
