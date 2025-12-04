#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        transform.py
 Author:      JP Ueberbach
 Created:     2025-11-09
 Description: Transform Dukascopy Historical JSON delta format into normalized OHLC CSV files.
              Supports vectorized computation, multiprocessing, and progress tracking.

 Usage:
     python3 transform.py

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - orjson

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import numpy as np
import orjson
import os
from datetime import date
from pathlib import Path

CACHE_PATH = "cache"              # Dukascopy cached Delta downloads are here
DATA_PATH = "data/transform/1m"   # Output path for the transformed files
TEMP_PATH = "data/temp"           # Today's live data is stored here
ROUND_DECIMALS = 8                # Round prices to this number of decimals

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
    cache_path = Path(CACHE_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")
    data_path = Path(DATA_PATH) / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.csv")
    temp_cache_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.json")
    temp_data_path = Path(TEMP_PATH) / dt.strftime(f"{symbol}_%Y%m%d.csv")

    is_historical = cache_path.is_file()

    if not is_historical:
        if temp_cache_path.is_file(): # Handles the case where no data exists
            # Live data
            cache_path = temp_cache_path
            data_path = temp_data_path
        else:
            # Should not happen
            raise FileNotFoundError

    if is_historical:
        # Remove (old) live data
        temp_cache_path.unlink(missing_ok=True)
        temp_data_path.unlink(missing_ok=True)

    # Load JSON market data
    with open(cache_path, "rb") as file:
        data = orjson.loads(file.read())

    # Vectorized computation of cumulative OHLC and timestamps
    times   = np.cumsum(np.array(data['times'], dtype=np.int64) * data['shift']) + data['timestamp']
    opens   = data['open']  + np.cumsum(np.array(data['opens'],  dtype=np.float64) * data['multiplier'])
    highs   = data['high']  + np.cumsum(np.array(data['highs'],  dtype=np.float64) * data['multiplier'])
    lows    = data['low']   + np.cumsum(np.array(data['lows'],   dtype=np.float64) * data['multiplier'])
    closes  = data['close'] + np.cumsum(np.array(data['closes'], dtype=np.float64) * data['multiplier'])
    volumes = np.array(data['volumes'], dtype=np.float64)

    # Get mask 0 volume candles (filter)
    mask = volumes != 0.0

    # Filter using mask
    times, opens, highs, lows, closes, volumes = [
        arr[mask] for arr in [times, opens, highs, lows, closes, volumes]
    ]

    # Create directory
    data_path.parent.mkdir(parents=True, exist_ok=True)

    # Create dataframe and round OHLC prices
    df = pd.DataFrame({
        'time': [str(t).replace('T', ' ')[:19] for t in np.array(times*1_000_000, dtype='datetime64[ns]')], # (Extreme) Performance optimization
        'open': np.round(opens, ROUND_DECIMALS),
        'high': np.round(highs, ROUND_DECIMALS),
        'low': np.round(lows, ROUND_DECIMALS),
        'close': np.round(closes, ROUND_DECIMALS),
        'volume': volumes
    })

    # Temporary location for output data
    temp_path = data_path.with_suffix('.tmp')

    # Write output
    df.to_csv(
        temp_path,
        index=False,
        header=True,
        sep=','
    )

    # Atomic
    os.replace(temp_path, data_path)

    return True


def fork_transform(args) -> bool:
    """
    Multiprocessing wrapper for transforming symbols.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, dt) to pass to transform_symbol.
    """
    symbol, dt = args

    transform_symbol(symbol, dt)
    
    return True
