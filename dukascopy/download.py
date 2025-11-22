#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        download.py
 Author:      JP Ueberbach
 Created:     2025-11-09
 Description: Download Dukascopy minute-level delta JSON candle (HST) data for all
              symbols listed in 'symbols.txt'. Supports historical and
              current-day downloads with automatic folder structure management.

 Usage:
     python3 download.py

 Requirements:
     - Python 3.8+
     - pandas
     - filelock
     - requests
     - tqdm

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import requests
import os
import math
from utils.locks import acquire_lock, release_lock
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from multiprocessing import get_context
from tqdm import tqdm

START_DATE = "2025-11-01"      # Historic download start date
NUM_PROCESSES = os.cpu_count() # Number of simultaneous downloads (parallelism)

CACHE_PATH = "cache"         # Cached data of download.py is stored here
TEMP_PATH = "data/temp"           # Today's live data is stored here

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



def download_symbol(symbol: str, dt: date) -> None:
    """
    Download Dukascopy minute-level delta JSON data for a given symbol and date.

    Handles both historical and current-day downloads:
        - Historical data is saved in '{CACHE_PATH}/YYYY/MM/'.
        - Current-day data is saved in '{TEMP_PATH}/'.
    Uses a file lock to prevent race conditions and partial files.

    Parameters
    ----------
    symbol : str
        Trading symbol to download.
    dt : date
        Date of the data to download.

    Notes
    -----
    - Currently, retries are not implemented.
    - Creates folders automatically if missing.
    """


    today_dt = datetime.now(timezone.utc).date()
    cache_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.json")

    if dt == today_dt:
        url = f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID"
    else:
        url = f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID/{dt.year}/{dt.month}/{dt.day}"
        if cache_path.is_file():
            cache_path.unlink(missing_ok=True)
        cache_path = Path(CACHE_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, headers={"Accept-Encoding": "gzip, deflate"})
        response.raise_for_status()
    except Exception:
        raise # raise for pool to capture
    else:
        temp_path = cache_path.with_suffix('.tmp')
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        os.replace(temp_path, cache_path)


def fork_download(args: tuple) -> None:
    """
    Multiprocessing wrapper to download a single symbol/date.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, dt) to pass to download_symbol.
    """
    symbol, dt = args
    try:
        acquire_lock(symbol, dt)

        download_symbol(symbol, dt)
    except Exception as e:
        # Download error is critical and we want to stop the pool, so we raise
        raise
    finally:
        release_lock(symbol, dt)


if __name__ == "__main__":
    print(f"Download - Dukascopy delta-json HTTP ({NUM_PROCESSES} parallelism)")

    symbols = load_symbols()

    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    today_dt = datetime.now(timezone.utc).date()

    dates = [start_dt + timedelta(days=i) for i in range((today_dt - start_dt).days + 1)]

    tasks = [
        (sym, dt)
        for dt in dates
        for sym in symbols
        if not Path(f"{CACHE_PATH}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.json").is_file()
    ]

    ctx = get_context("fork")
    with ctx.Pool(processes=NUM_PROCESSES) as pool:
        chunksize = max(1, min(32, math.floor(math.sqrt(len(tasks)) / NUM_PROCESSES)))
        for _ in tqdm(pool.imap_unordered(fork_download, tasks, chunksize=chunksize),
                      total=len(tasks), unit='downloads', colour='white'):
            pass

    print(f"Done. Downloaded {len(tasks)} files.")
