#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        transform.py
 Author:      JP Ueberbach
 Created:     2025-11-09
 Description: Transform Dukascopy JSON market data (HST) into normalized OHLC CSV files.
              Supports vectorized computation, multiprocessing, and progress tracking.

 Usage:
     python3 transform.py

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - filelock
     - orjson
     - tqdm

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import numpy as np
import orjson
import os
import math
from utils.locks import acquire_lock, release_lock
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from multiprocessing import get_context
from tqdm import tqdm

START_DATE = "2025-11-01"         # Historic data start
NUM_PROCESSES = os.cpu_count()    # Use all CPU cores for parallel processing

CACHE_PATH = "cache"                # Dukascopy cached HST downloads are here
DATA_PATH = "data/transform/1m"     # Output path for the transformed files
TEMP_PATH = "data/temp"                  # Today's live data is stored here
ROUND_DECIMALS = 8                  # Round prices to this number of decimals

def load_symbols() -> pd.Series:
    """
    Load and normalize trading symbols from 'symbols.txt'.

    Converts symbols to string format and replaces '/' with '-' for
    consistent file naming.

    Returns
    -------
    pd.Series
        Series of normalized trading symbols.
    """
    df = pd.read_csv('symbols.txt')
    return df.iloc[:, 0].astype(str).str.replace('/', '-', regex=False)


def transform_symbol(symbol: str, dt: date) -> bool:
    """
    Transform a single symbol's JSON market data into a normalized OHLC CSV.

    The function:
        - Loads JSON data from 'cache' or 'temp'.
        - Computes OHLC using vectorized numpy operations.
        - Writes CSV atomically to avoid race conditions.

    Parameters
    ----------
    symbol : str
        Trading symbol to transform.
    dt : date
        Date of the data to process.

    Returns
    -------
    bool
        True if transformation succeeded, False otherwise.
    """
    try:
        acquire_lock(symbol, dt)

        cache_path = Path(CACHE_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")
        data_path = Path(DATA_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.csv")
        temp_cache_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.json")
        temp_data_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.csv")

        # Prefer cached JSON files
        if not cache_path.is_file():
            if not temp_cache_path.is_file():
                return False
            
            cache_path = temp_cache_path
            data_path = temp_data_path
        else:
            temp_cache_path.unlink(missing_ok=True)
            temp_data_path.unlink(missing_ok=True)

        try:
            # Load JSON market data
            with open(cache_path, "rb") as file:
                data = orjson.loads(file.read())
        except Exception as e:
            tqdm.write(f"Error reading {cache_path}: {e}")
            return False

        # Vectorized computation of cumulative OHLC and timestamps
        times   = np.cumsum(np.array(data['times'], dtype=np.int64) * data['shift']) + data['timestamp']
        opens   = data['open']  + np.cumsum(np.array(data['opens'],  dtype=np.float64) * data['multiplier'])
        highs   = data['high']  + np.cumsum(np.array(data['highs'],  dtype=np.float64) * data['multiplier'])
        lows    = data['low']   + np.cumsum(np.array(data['lows'],   dtype=np.float64) * data['multiplier'])
        closes  = data['close'] + np.cumsum(np.array(data['closes'], dtype=np.float64) * data['multiplier'])
        volumes = np.array(data['volumes'], dtype=np.float64)

        mask = volumes != 0.0

        times, opens, highs, lows, closes, volumes = [
            arr[mask] for arr in [times, opens, highs, lows, closes, volumes]
        ]

        # End BUG-fix

        data_path.parent.mkdir(parents=True, exist_ok=True)
        ohlc = np.round(np.column_stack((opens, highs, lows, closes)), ROUND_DECIMALS)

        try:
            temp_path = data_path.with_suffix('.tmp')
            np.savetxt(
                temp_path,
                np.column_stack((
                    pd.to_datetime(times, unit='ms').astype(str),
                    ohlc,
                    volumes
                )),
                fmt="%s",
                delimiter=",",
                header="time,open,high,low,close,volume",
                comments=''
            )
            os.replace(temp_path, data_path)  # Atomic overwrite
        except Exception as e:
            tqdm.write(f"Write failed {symbol} {dt}: {e}")
            temp_path.unlink(missing_ok=True)
            return False

    except KeyboardInterrupt:
        tqdm.write(f"Interrupted by user")
        return False
    finally:
        release_lock(symbol, dt)

    return True


def fork_transform(args):
    """
    Multiprocessing wrapper for transforming symbols.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, dt) to pass to transform_symbol.
    """
    symbol, dt = args
    transform_symbol(symbol, dt)


if __name__ == "__main__":
    print(f"Transform - Dukascopy delta-json to OHLC CSV ({NUM_PROCESSES} parallelism)")
    symbols = load_symbols()

    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    today_dt = datetime.now(timezone.utc).date()

    # Generate all dates to process
    dates = [start_dt + timedelta(days=i) for i in range((today_dt - start_dt).days + 1)]

    # Create task list (symbol, date) for all missing CSV files
    tasks = [
        (sym, dt)
        for dt in dates
        for sym in symbols
        if not Path(f"{DATA_PATH}/{dt:%Y}/{dt:%m}/{sym}_{dt:%Y%m%d}.csv").is_file()
    ]

    # Multiprocessing pool with progress bar
    ctx = get_context("spawn")
    with ctx.Pool(processes=NUM_PROCESSES) as pool:
        chunksize = max(1, min(128, int(math.sqrt(len(tasks)) / NUM_PROCESSES) or 1))
        for _ in tqdm(pool.imap_unordered(fork_transform, tasks, chunksize=chunksize),
                      total=len(tasks), unit='file', colour='white'):
            pass

    print(f"Done. Transformed {len(tasks)} files.")
