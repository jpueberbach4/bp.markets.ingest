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
     - requests

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import requests
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

CACHE_PATH = "cache"           # Directory where historical data files are stored
TEMP_PATH = "data/temp"        # Directory for storing today's live data

MAX_RETRIES = 3                # Number of retry attempts for failed downloads
BACKOFF_FACTOR = 2             # Exponential backoff multiplier for retry delays

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



def download_symbol(symbol: str, dt: date) -> bool:
    """
    Download Dukascopy minute-level delta JSON data for a given symbol and date.

    Handles both historical and current-day downloads:
        - Historical data is saved in '{CACHE_PATH}/YYYY/MM/'.
        - Current-day data is saved in '{TEMP_PATH}/'.

    Parameters
    ----------
    symbol : str
        Trading symbol to download.
    dt : date
        Date of the data to download.

    Returns
    -------
    bool
        True if new data was successfully downloaded.

    Notes
    -----
    - Retries are implemented.
    - Creates folders automatically if missing.
    """
    today_dt = datetime.now(timezone.utc).date()

    # Build output file paths for historical vs. live data
    cache_path = Path(CACHE_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")
    cache_temp_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.json")

    if dt == today_dt:
        url = f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID"
        # Save live (current-day) data to the temporary directory
        cache_path = cache_temp_path
    else:
        url = f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID/{dt.year}/{dt.month}/{dt.day}"
        # If a temp file exists for this date, remove it since it's now historical
        if cache_temp_path.is_file():
            cache_temp_path.unlink(missing_ok=True)
        cache_path = Path(CACHE_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")

    # Attempt the download with retry logic
    for attempt in range(MAX_RETRIES):
        try:
            # Perform HTTP GET request
            response = requests.get(url, 
                headers={
                    "Accept-Encoding": "gzip, deflate",
                    "User-Agent": "dukascopy-downloader/1.0 (+https://github.com/jpueberbach4/bp.markets.ingest/blob/main/dukascopy/download.py)"
                },
                timeout=10
            )
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                # Check whether the error is temporary (rate limit or server error)
                status_code = getattr(e.response, 'status_code', 0)
                if status_code >= 500 or status_code == 429: # 429: Too Many Requests
                    wait_time = BACKOFF_FACTOR ** attempt
                    print(f"Transient error {status_code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Non-retriable error (e.g., 404); propagate failure
                    raise e
            else:
                # Final retry failed; propagate exception
                raise e

    # Ensure destination directory exists
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    temp_path = cache_path.with_suffix('.tmp')
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    
    # Atomic
    os.replace(temp_path, cache_path)

    return True


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
        download_symbol(symbol, dt)
    except Exception as e:
        raise
    finally:
        pass
