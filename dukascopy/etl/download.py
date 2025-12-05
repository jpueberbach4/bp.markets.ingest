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
import orjson
import numpy as np
from datetime import date, datetime, timezone
from pathlib import Path
from config.app_config import AppConfig, DownloadConfig, load_app_config

ENABLE_BACKFILL_FILTER = True  # We do not support backfilling atm. Forward only pipeline.

session = None                 # Session per worker

def download_filter_backfilled_items(temp_path: Path, cache_path: Path) -> bool:
    """
    Merges new data from a temporary file into a cached dataset while skipping backfilled items.

    This function ensures that only data **occurring after the last timestamp in the cache** is appended
    from the temporary dataset. Any overlapping or backfilled entries are ignored. The function uses
    cumulative sums of the `"times"` array, adjusted by the `"shift"` and `"timestamp"` values, to 
    compute the cutoff for new data.

    Args:
        temp_path (Path): Path to the temporary file containing new data in JSON format.
        cache_path (Path): Path to the cached file containing existing data in JSON format.

    Returns:
        bool: 
            - True if new data was appended to the cache.  
            - False if no new data was found or if the cache does not exist.

    Raises:
        Exception: Propagates any exception encountered during reading, processing, or writing.

    Notes:
        - Both files are expected to be in `orjson` JSON format, containing the keys:
          `"times"`, `"opens"`, `"highs"`, `"lows"`, `"closes"`, `"volumes"`, `"shift"`, and `"timestamp"`.
        - Uses vectorized NumPy operations for efficiency.
        - The temporary file is updated in-place with the merged result.
        - Errors are printed for debugging before being re-raised.
    """
    if not cache_path.exists():
        return False

    try:
        with open(temp_path, "r+b") as f_temp, open(cache_path, "rb") as f_cache:
            # Read and parse data
            data_temp = orjson.loads(f_temp.read())
            data_cache = orjson.loads(f_cache.read())

            # Rollover can be cache.times = [], skip this routine, just use temp
            if not len(data_cache['times']):
                return False

            # Precompute cumulative sums (vectorized)
            cut_off = (np.cumsum(np.array(data_cache['times'], dtype=np.int64) * data_cache['shift']) + data_cache['timestamp'])[-1]
            times_temp = (np.cumsum(np.array(data_temp['times'], dtype=np.int64) * data_temp['shift']) + data_temp['timestamp'])

            # Get mask (filter)
            mask = times_temp > cut_off

            # Find first index where temp data exceeds cutoff (vectorized)
            indices = np.where(mask)[0]
            idx = indices[0] if indices.size > 0 else None

            if idx is not None:
                # If appendable rows, extend
                for column in ["times","opens","highs","lows","closes","volumes"]:
                    # Bulk extend all columns at once instead of nested loops
                    data_cache[column].extend(data_temp[column][idx:])

            # Write back optimized - single seek/truncate/write operation
            f_temp.seek(0)
            f_temp.truncate(0)
            f_temp.write(orjson.dumps(data_cache))
        
        return True
    except Exception as e:
        # Log error for debugging
        raise e

def download_symbol(symbol: str, dt: date, app_config: AppConfig) -> bool:
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
    app_config : AppConfig
        Config object.

    Returns
    -------
    bool
        True if new data was successfully downloaded.

    Notes
    -----
    - Retries are implemented.
    - Creates folders automatically if missing.
    """
    global session # Session per worker

    if session is None:
        session = requests.Session()   # Create session ONCE per worker

    config = app_config.download

    today_dt = datetime.now(timezone.utc).date()

    # Build output file paths for historical vs. live data
    historical_archive_path = Path(config.paths.historic) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")
    live_staging_path = Path(config.paths.live) / dt.strftime(f"{symbol}_%Y%m%d.json")

    is_historical = not dt == today_dt

    if not is_historical:
        url = f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID"
        # The final file is the live staging file (mutable)
        final_target_path = live_staging_path
    else:
        url = f"https://jetta.dukascopy.com/v1/candles/minute/{symbol}/BID/{dt.year}/{dt.month}/{dt.day}"
        # The final file is the historical archive file (immutable)
        final_target_path = historical_archive_path

    # Attempt the download with retry logic
    for attempt in range(config.max_retries):
        try:
            # Perform HTTP GET request
            response = session.get(url, 
                headers={
                    "Accept-Encoding": "gzip, deflate",
                    "User-Agent": "dukascopy-downloader/1.0 (+https://github.com/jpueberbach4/bp.markets.ingest/blob/main/dukascopy/download.py)"
                },
                timeout=config.timeout
            )
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt < config.max_retries - 1:
                # Check whether the error is temporary (rate limit or server error)
                status_code = getattr(e.response, 'status_code', 0)
                if status_code >= 500 or status_code == 429: # 429: Too Many Requests
                    wait_time = config.backoff_factor ** attempt
                    print(f"Transient error {status_code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Non-retriable error (e.g., 404); propagate failure
                    raise e
            else:
                # Final retry failed; propagate exception
                raise e

    # Ensure destination directory exists (based on final_target_path)
    final_target_path.parent.mkdir(parents=True, exist_ok=True)
        
    # Write output to the temporary file (.tmp suffix)
    download_tmp_path = final_target_path.with_suffix('.tmp')
    with open(download_tmp_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    
    if ENABLE_BACKFILL_FILTER:
        # Determine the existing file state to use as the cut-off source
        filter_source_path = historical_archive_path # Default to archive path

        if live_staging_path.is_file():
            # If the staging file exists, use it as the source of truth for continuity.
            # This is CRITICAL for the rollover from live -> historical.
            filter_source_path = live_staging_path

        download_filter_backfilled_items(download_tmp_path, filter_source_path)

    # Atomic swap: Overwrite the final destination with the clean, merged data.
    os.replace(download_tmp_path, final_target_path)

    # Remove historical item from live folder if exists (completing the rollover)
    if is_historical:
        if live_staging_path.is_file():
            live_staging_path.unlink(missing_ok=True)

    return True


def fork_download(args: tuple) -> bool:
    """
    Multiprocessing wrapper to download a single symbol/date.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, dt, config) to pass to download_symbol.
    """
    symbol, dt, app_config = args
    
    download_symbol(symbol, dt, app_config)

    return True
