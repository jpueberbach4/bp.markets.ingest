#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resample.py
 Author:      JP Ueberbach
 Created:     2025-11-15
 Description: This script processes symbol CSV files incrementally using saved read/write
              offsets. It supports multiple cascading timeframes (e.g., 1m → 5m → 15m → 30m → 1h)
              without re-reading or re-writing previously processed data.

 Usage:
     python3 resample.py

 Requirements:
     - Python 3.8+
     - Pandas
     - tqdm

 License:
     MIT License
===============================================================================
"""

import os
import pandas as pd
from pathlib import Path
from multiprocessing import get_context
from tqdm import tqdm
from io import StringIO

# Configuration for each cascading timeframe
CONFIG = [
    {
        "timeframe": "5m",
        "input": "data/aggregate/1m",
        "output": "data/resample/5m",
        "index": "data/resample/5m/index",
        "seconds": 300
    },
    {
        "timeframe": "15m",
        "input": "data/resample/5m",
        "output": "data/resample/15m",
        "index": "data/resample/15m/index",
        "seconds": 900
    },
    {
        "timeframe": "30m",
        "input": "data/resample/15m",
        "output": "data/resample/30m",
        "index": "data/resample/30m/index",
        "seconds": 1800
    },
    {
        "timeframe": "1h",
        "input": "data/resample/30m",
        "output": "data/resample/1h",
        "index": "data/resample/1h/index",
        "seconds": 3600
    },
    {
        "timeframe": "4h",
        "input": "data/resample/1h",
        "output": "data/resample/4h",
        "index": "data/resample/4h/index",
        "seconds": 14400
    },
    {
        "timeframe": "8h",
        "input": "data/resample/4h",
        "output": "data/resample/8h",
        "index": "data/resample/8h/index",
        "seconds": 28800
    }
]

NUM_PROCESSES = os.cpu_count()      


def load_symbols() -> pd.Series:
    """
    Load and normalize trading symbols from 'symbols.txt'.

    Symbols may contain slashes like "BTC/USDT". These are converted into a
    filesystem-safe format like "BTC-USDT".

    Returns
    -------
    pd.Series
        A Series of normalized symbol strings.
    """
    df = pd.read_csv('symbols.txt')
    return df.iloc[:, 0].astype(str).str.replace('/', '-', regex=False)


def resample_symbol(symbol: str) -> bool:
    """
    Incrementally resample a single symbol through each configured timeframe.

    The function:

    - Loads and updates read/write offsets from an index file.
    - Reads the input CSV in batches.
    - Adds an "offset" column to each batch row so we know where the raw candle
      originated in the file. This enables identifying the last candle that
      contributed to the resampled output.
    - Resamples using pandas' `.resample()` into a higher timeframe.
    - Always rewrites the last candle because it may be incomplete.
    - Writes updated offsets atomically to avoid partial writes.

    Parameters
    ----------
    symbol : str
        The trading symbol (normalized, e.g., "BTC-USDT").

    Returns
    -------
    bool
        Always returns False for now, but may be extended for status reporting.
    """
    for config in CONFIG:
        timeframe, input, output, index, seconds = config.values()

        # Construct file paths
        input_path = Path(f"{input}/{symbol}.csv")
        index_path = Path(f"{index}/{symbol}.idx")
        output_path = Path(f"{output}/{symbol}.csv")

        # Ensure index file exists (stores input/output file offsets)
        if not index_path.exists():
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, 'w') as f_idx:
                f_idx.write("0\n0")  # input_offset, output_offset

        # Load the saved offsets
        with open(index_path, 'r') as f_idx:
            input_position, output_position = [
                int(line.strip()) for line in f_idx.readlines()[:2]
            ]

        # Ensure output file exists
        if not output_path.exists():
            with open(output_path, "w"):
                pass

        with open(input_path, "r") as f_input, open(output_path, "r+") as f_output:

            # Always read the header from input file
            header = f_input.readline()

            # Seek to previously processed point
            if input_position > 0:
                f_input.seek(input_position)

            # If output file is new, write the header
            if output_position == 0:
                f_output.write(header)
                output_position = f_output.tell()

            BATCH_SIZE = 500_000
            THE_END = False

            while True:
                # Create batch including header + offset column name
                batch = [f"{header.strip()},offset\n"]

                # Read a chunk of lines along with their raw input offsets
                for _ in range(BATCH_SIZE):
                    offset_before = f_input.tell()
                    line = f_input.readline()

                    if not line:
                        THE_END = True
                        break

                    batch.append(f"{line.strip()},{offset_before}\n")

                # Load into DataFrame
                df = pd.read_csv(
                    StringIO(''.join(batch)),
                    names=["time", "open", "high", "low", "close", "volume", "offset"],
                    header=0
                )

                # Convert time column
                df['time'] = pd.to_datetime(df['time'], format="%Y-%m-%d %H:%M:%S")
                df.set_index('time', inplace=True)

                # Fill gaps in raw OHLC data before resampling
                df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].ffill()

                # Resample into target timeframe
                resampled = df.resample(f'{seconds}S').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'offset': 'first'  # identifies source raw candle for the window
                }).ffill()

                # Round numerical values to avoid floating drift
                resampled = resampled.round(8)

                # Determine new input_position:
                # The last resampled row always comes from the last "offset" in the batch.
                input_position = resampled.iloc[-1]['offset']

                # filter zero volume
                resampled = resampled[resampled['volume'] != 0]

                # Rewrite the output file from its last known position
                f_output.seek(output_position)
                f_output.truncate(output_position)

                # Remove offset column before writing out
                resampled.drop(columns=["offset"], inplace=True)

                # Write all but last candle (fully complete)
                f_output.write(resampled.iloc[:-1].to_csv(index=True, header=False))

                # Update output position
                output_position = f_output.tell()

                # Write the last candle (may still be incomplete)
                f_output.write(resampled.tail(1).to_csv(index=True, header=False))

                # Write updated offsets atomically
                index_temp_path = Path(f"{index_path}.tmp")
                with open(index_temp_path, "w") as f_idx:
                    f_idx.write(f"{int(input_position)}\n{int(output_position)}")
                    f_idx.flush()
                os.replace(index_temp_path, index_path)

                # Stop if EOF reached
                if THE_END:
                    break

                # Seek to updated offsets for next loop
                f_input.seek(input_position)
                f_output.seek(output_position)


    return False


def fork_resample(args):
    """
    Process all dates for a single symbol sequentially.

    Intended for use with multiprocessing where each worker handles
    one symbol over the full date range.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, list of dates).
    """
    symbol, = args
    resample_symbol(symbol)

if __name__ == "__main__":
    print(f"Resample - Cascaded resampling from 1m CSV -> 5m -> 15m -> 30m -> ... ({NUM_PROCESSES} parallelism)")
    symbols = load_symbols()

    tasks = [(symbol,) for symbol in symbols]

    ctx = get_context("spawn")
    with ctx.Pool(processes=NUM_PROCESSES) as pool:
        for _ in tqdm(pool.imap_unordered(fork_resample, tasks, chunksize=1),
                      total=len(tasks), unit='symbols', colour='white'):
            pass

    print(f"Done. Resampled {len(tasks)} symbols.")