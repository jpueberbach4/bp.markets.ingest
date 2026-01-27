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


def require_tos_acceptance():
    """
    Prompts the user to accept the Terms of Service and loops until a 
    valid affirmative response ('yes' or 'y') is received, or exits on denial.
    """

    if Path("cache/HAS_ACCEPTED_TERMS_OF_SERVICE").exists():
        return True

    print("\n" + "="*70)
    print("🚀 TERMS OF SERVICE")
    print("="*70)
    print("""
1. This tool provides access to Dukascopy Bank SA's historical data.
2. Data is for PERSONAL, NON-COMMERCIAL research/analysis ONLY.
3. REDISTRIBUTION IN ANY FORM IS STRICTLY PROHIBITED.
4. You accept full liability for your usage.
5. Dukascopy's own Terms of Service apply.
6. THE TOOL AND DATA ARE PROVIDED 'AS IS' WITHOUT ANY WARRANTIES, 
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF 
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR ACCURACY.
    
By using this tool, you accept these terms.
    """)
    # Loop indefinitely until a valid input is provided
    while True:
        # Prompt the user for input and convert to lowercase for easy checking
        response = input("\nDo you accept the Terms of Service? (yes/no): ").strip().lower()

        if response in ['yes', 'y']:
            print("\n✓ Terms accepted. Continuing with data extraction...")
            # Ensure cache directory exists
            Path("cache").mkdir(parents=True, exist_ok=True)
            with open("cache/HAS_ACCEPTED_TERMS_OF_SERVICE", "w"):
                pass
            return True  # Return success
            
        elif response in ['no', 'n']:
            print("\n✗ Terms were not accepted. Aborting.")
            sys.exit(1) # Exit the script with a non-zero status code (error)
            
        else:
            print("Invalid input. Please respond with 'yes' or 'no'.")


def main():
    """
    Main entry point for running the Dukascopy ETL pipeline.

    Steps:
    1. Load symbols and generate tasks based on missing files
    2. Execute download, transform, and aggregate stages in parallel using a single pool
    3. Measure and report total runtime
    """
    # TOS acceptance
    try:
        require_tos_acceptance()
    except KeyboardInterrupt:
        sys.exit(1)

    # Record wall-clock start time
    start_time = time.time()  
    # Load YAML config (currently only resample support)
    app_config = load_config()
    # Get orchestrator configuration
    config = app_config.orchestrator

    # Determine num_processes
    num_processes = os.cpu_count() if config.num_processes is None else config.num_processes

    # Splash message
    print(f"Running Dukascopy ETL pipeline ({num_processes} processes)")

    # Allocate exclusive lock
    RUN_LOCK = Path(f"{config.paths.locks}/run.lock")
    print(f"Using lockfile {RUN_LOCK}")
    RUN_LOCK.parent.mkdir(parents=True,exist_ok=True)
    lock = FileLock(RUN_LOCK)
    try:
        if not NOLOCK:
            lock.acquire(timeout=1)
    except Timeout:
        # Error out if could not acquire lock (instance already running)
        print("Another instance is running. Exiting.")
        return

    try:
        # Load trading symbols from symbols.txt
        symbols = load_symbols()

        # This is an older backward incompatability protection (can be removed eventually)
        if not len(app_config.resample.timeframes):
            print("Notice, there were breaking config changes! See README for more information!")
            sys.exit(1)

        # Generate list of dates to process (from START_DATE to today UTC)
        start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()
        today_dt = datetime.now(timezone.utc).date()
        dates = [start_dt + timedelta(days=i) for i in range((today_dt - start_dt).days + 1)]

        # Prepare download tasks for JSON files that are missing
        download_tasks = [
            (sym, dt, app_config)
            for dt in dates
            for sym in symbols
            if not Path(f"{config.paths.downloads}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.json").is_file()
        ]

        # Download disable option support
        if config.disable_download: download_tasks = []

        # Prepare transform tasks for CSV files that are missing
        if not config.disable_download:
            transform_tasks = [
                (sym, dt, app_config)
                for dt in dates
                for sym in symbols
                if not Path(f"{config.paths.transforms}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.bin").is_file()
            ]
        else:
            transform_tasks = [
                (sym, dt, app_config)
                for dt in dates
                for sym in symbols
                if not Path(f"{config.paths.transforms}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.bin").is_file()
                if Path(f"{config.paths.downloads}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.json").is_file()
            ]            

        # Prepare aggregate tasks (one per symbol, covering all dates)
        aggregate_tasks = [(sym, dates, app_config) for sym in symbols]

        # Prepare resample tasks (one per symbol)
        resample_tasks = [(symbol, app_config) for symbol in symbols]

        # Create a single multiprocessing context to minimize process spawn overhead
        ctx = get_context("fork")
        pool = ctx.Pool(processes=num_processes)

        # Define pipeline stages with associated task lists and chunk sizes
        stages = [
            (
                "Download",
                download.fork_download,
                download_tasks,
                max(1, min(32, math.floor(math.sqrt(len(download_tasks)) / num_processes))),
                "downloads"
            ),
            (
                "Transform",
                transform.fork_transform,
                transform_tasks,
                max(1, min(128, int(math.sqrt(len(transform_tasks)) / num_processes) or 1)),
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
                    import traceback
                    traceback.print_exc()
                    break

        # Report total wall-clock runtime
        elapsed = time.time() - start_time
        print("\nETL pipeline complete!")
        print(f"Total runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
    finally:
        lock.release()


if __name__ == "__main__":
    main()
