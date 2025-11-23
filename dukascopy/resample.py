#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resample.py
 Author:      JP Ueberbach
 Created:     2025-11-15
 Description:
     
     Incremental, crash-resilient OHLCV resampling engine for append-only
     time-series data. Each symbol's raw CSV file grows strictly by appending
     new rows, and previously written data never changes. The script uses
     forward-moving byte offsets to resume processing exactly where it left
     off, without ever re-reading or re-writing completed candles. The last
     resampled candle is always considered (potentially incomplete).

     Core properties:

         • Append-only input model:
             Raw symbol CSVs are strictly append-only. Byte offsets stored in
             per-symbol index files remain permanently valid.

         • Deterministic incremental resampling:
             New rows are processed in batches, aggregated into higher
             timeframes (1m → 5m → 15m → 30m → 1h → …), and written exactly
             once. Finished candles are never touched again.

         • Crash-safe last-candle rewrite:
             Only the final, potentially incomplete resampled candle is ever
             truncated and regenerated. On restart, the engine reconstructs
             this candle from upstream offsets with no risk of corrupting any
             historical output.

         • Zero backtracking:
             The pipeline never reprocesses historical data, never scans from
             the beginning of a file, and never rewrites completed output.

         • Cascading multi-timeframe pipeline:
             Each timeframe resamples from the output of the previous one,
             forming a forward-only DAG of incremental transformations.
             
             Note: Monthly candles are resampled from daily data rather than
             weekly data to ensure proper alignment, since weeks often
             span two calendar months.

     The result is a high-performance, low-IO, idempotent resampling system
     designed for large datasets and continuous ingestion.

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
from datetime import datetime, timezone
from pathlib import Path
from multiprocessing import get_context
from tqdm import tqdm
from io import StringIO
from typing import Tuple, IO

VERBOSE = os.getenv('VERBOSE', '0').lower() in ('1', 'true', 'yes', 'on')

BATCH_SIZE = 250_000    # Number of raw candles to read per incremental batch.
ROUND_DECIMALS = 8      # Round prices to this number of decimals

# Configuration for each cascading timeframe
CONFIG = [
    {
        "timeframe": "5m",
        "input": "data/aggregate/1m",
        "output": "data/resample/5m",
        "index": "data/resample/5m/index",
        "rule": "5T",
        "label": "left",
        "closed": "left"
    },
    {
        "timeframe": "15m",
        "input": "data/resample/5m",
        "output": "data/resample/15m",
        "index": "data/resample/15m/index",
        "rule": "15T",
        "label": "left",
        "closed": "left"
    },
    {
        "timeframe": "30m",
        "input": "data/resample/15m",
        "output": "data/resample/30m",
        "index": "data/resample/30m/index",
        "rule": "30T",
        "label": "left",
        "closed": "left"
    },
    {
        "timeframe": "1h",
        "input": "data/resample/30m",
        "output": "data/resample/1h",
        "index": "data/resample/1h/index",
        "rule": "1H",
        "label": "left",
        "closed": "left"
    },
    {
        "timeframe": "4h",
        "input": "data/resample/1h",
        "output": "data/resample/4h",
        "index": "data/resample/4h/index",
        "rule": "4H",
        "label": "left",
        "closed": "left"
    },
    {
        "timeframe": "8h",
        "input": "data/resample/4h",
        "output": "data/resample/8h",
        "index": "data/resample/8h/index",
        "rule": "8H",
        "label": "left",
        "closed": "left"
    },
    {
        "timeframe": "1d",
        "input": "data/resample/8h",
        "output": "data/resample/1d",
        "index": "data/resample/1d/index",
        "rule": "1D",
        "label": "left",
        "closed": "left"
    },
    # Weekly: use W-SAT in UTC to include full Friday trading
    {
        "timeframe": "1W",
        "input": "data/resample/1d",
        "output": "data/resample/1W",
        "index": "data/resample/1W/index",
        "rule": "W-SAT",
        "label": "left",
        "closed": "left"
    },
    # Monthly: can use start-of-month (MS) or last business day approach
    {
        "timeframe": "1M",
        "input": "data/resample/1d",
        "output": "data/resample/1M",
        "index": "data/resample/1M/index",
        "rule": "MS",
        "label": "left",
        "closed": "left"
    },
    # Yearly: start-of-year (AS)
    {
        "timeframe": "1Y",
        "input": "data/resample/1M",
        "output": "data/resample/1Y",
        "index": "data/resample/1Y/index",
        "rule": "AS",
        "label": "left",
        "closed": "left"
    }
]

NUM_PROCESSES = os.cpu_count()      


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



def resample_read_index(index_path: Path) -> Tuple[int, int]:
    """
    Read the incremental resampling index file and return the stored offsets.

    Parameters
    ----------
    index_path : Path
        Path to the `.idx` file storing the resampler's progress for a single
        symbol and timeframe. The file contains exactly two lines:
            1) input_position  – byte offset in the upstream CSV already processed
            2) output_position – byte offset in the output CSV already written

    Returns
    -------
    Tuple[int, int]
        (input_position, output_position), both guaranteed to be integers.

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
        resample_write_index(index_path, 0, 0)
        return 0, 0
    
    with open(index_path, 'r') as f_idx:
        lines = f_idx.readlines()[:2]
        if len(lines) != 2:
            raise
        input_position, output_position = [
            int(line.strip()) for line in lines
        ]
    return input_position, output_position

def resample_write_index(index_path: Path, input_position: int, output_position: int) -> bool:
    """
    Atomically persist updated read/write offsets for a symbol's resampling state.

    This function writes the incremental processing offsets
    (the raw-input byte offset and the resampled-output byte offset)
    using a crash-safe, atomic replace:

        1. A temporary file "<index_path>.tmp" is written containing:
               <input_position>
               <output_position>

        2. The temporary file is flushed and fsync-safe at the Python level.

        3. os.replace() is used to atomically overwrite the existing index file.

    Atomic replacement guarantees that:
        • The index file is always either the old valid version or the new one.
        • A crash, power loss, or kill signal cannot leave a partial write.
        • Offsets are never corrupted, preserving the append-only invariant.

    Parameters
    ----------
    index_path : Path
        Path to the index file storing incremental resampling offsets
        (input_position on line 1, output_position on line 2).

    input_position : int
        Byte-offset in the append-only input CSV marking the first unprocessed row.

    output_position : int
        Byte-offset in the resampled output CSV where new data should be appended.

    Returns
    -------
    bool
        Always returns True for now, indicating that the atomic write completed.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_temp_path = Path(f"{index_path}.tmp")
    with open(index_temp_path, "w") as f_idx:
        f_idx.write(f"{input_position}\n{output_position}")
        f_idx.flush()

    os.replace(index_temp_path, index_path)
    return True

def resample_batch_read(f_input: IO, header: str) -> Tuple[StringIO, bool]:
    """
    Read a batch of lines from an input file-like object while recording their byte offsets.

    This function reads up to `BATCH_SIZE` lines from `f_input`, capturing the file offset
    immediately before each line is read. It writes the resulting rows—along with an added
    `offset` column—into a `StringIO` buffer that begins with the provided header plus the
    new column name.

    Parameters
    ----------
    f_input : IO
        A file-like object opened for reading. Must support `tell()` and `readline()`.
    header : str
        The CSV header line to be written first in the output, without the `offset` column.

    Returns
    -------
    Tuple[StringIO, bool]
        A tuple containing:
        - A `StringIO` object positioned at the beginning, containing the header and batch data.
        - A boolean indicating whether end-of-file was reached during this read.
    """
    sio = StringIO()
    sio.write(f"{header.strip()},offset\n")

    eof_reached = False

    # Read a chunk of lines along with their raw input offsets
    for _ in range(BATCH_SIZE):
        offset_before = f_input.tell()
        line = f_input.readline()
        if not line:
            eof_reached = True
            break
        sio.write(f"{line.strip()},{offset_before}\n")
    
    sio.seek(0)

    return sio, eof_reached

def resample_batch(sio: StringIO, rule: str, label: str, closed: str) -> Tuple[pd.DataFrame, int]:
    """
    Resample a batch of OHLCV rows (with byte-offset tracking) into a higher timeframe.

    Parameters
    ----------
    sio : StringIO
        An in-memory CSV chunk containing raw 1m (or upstream) candles plus an
        appended `offset` column. The first line must contain the header.
    rule : str
        Pandas resampling rule (e.g., "5T", "15T", "1H", "1D").
    label : str
        Whether the resampled window label is placed on the 'left' or 'right' edge.
    closed : str
        Which side of the resample window is closed ('left' or 'right').

    Returns
    -------
    pd.DataFrame
        A resampled OHLCV DataFrame with:
            - open:   first value in window
            - high:   maximum value in window
            - low:    minimum value in window
            - close:  last value in window
            - volume: sum of volumes in window
            - offset: first byte offset of contributing raw rows
        All numeric fields are rounded to `ROUND_DECIMALS`.
    int
        Offset of last raw contributing candle (next input offset)

    Notes
    -----
    This function performs **no I/O**. It operates on a single in-memory batch
    and is used by the incremental resampling engine. The `offset` field is
    critical for crash-safe reconstruction of the final (possibly incomplete)
    candle, enabling precise forward-only incremental processing.
    """
    # Load into DataFrame
    df = pd.read_csv(
        sio,
        header=0,
        parse_dates=["time"],
        index_col="time"
    )

    # Resample into target timeframe
    resampled = df.resample(rule, label=label, closed=closed).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'offset': 'first'  # identifies source raw candle for the window
    })

    # Offset points to the position of the first raw input record that forms this row 
    next_input_position = int(resampled.iloc[-1]['offset'])

    # Remove offset column immediately
    resampled.drop(columns=["offset"], inplace=True)

    # Round numerical values to avoid floating drift
    resampled = resampled.round(ROUND_DECIMALS)

    # Filter zero volume
    resampled = resampled[resampled['volume'].notna() & (resampled['volume'] != 0)]

    # Force date-format YYYY-MM-DD HH:MM:SS (might drop time on 1D)
    resampled.index = resampled.index.strftime("%Y-%m-%d %H:%M:%S")

    # Return the resampled dataframe
    return resampled, next_input_position


def resample_symbol(symbol: str) -> bool:
    """
    Incrementally resample a single symbol through each configured timeframe.

    The function:

    - Loads and updates read/write offsets from an index file.
    - Reads the input CSV in batches.
    - Resamples into a higher timeframe.
    - Always rewrites the last candle because it may be incomplete.
    - Writes updated offsets atomically to avoid partial writes.

    Parameters
    ----------
    symbol : str
        The trading symbol (normalized, e.g., "BTC-USDT").

    Returns
    -------
    bool
        Always returns True for now, but may be extended for status reporting.
    """
    for i, config in enumerate(CONFIG):

        timeframe, input_dir, output_dir, index_dir, rule, label, closed = (
            config[k] for k in ("timeframe", "input", "output", "index", "rule","label","closed")
        )

        if VERBOSE:
            tqdm.write(f"  → {symbol}: {config['timeframe']} ({i+1}/{len(CONFIG)})")

        # Construct file paths
        input_path = Path(f"{input_dir}/{symbol}.csv")
        index_path = Path(f"{index_dir}/{symbol}.idx")
        output_path = Path(f"{output_dir}/{symbol}.csv")

        # Ensure input path exists
        if not input_path.exists():
            if VERBOSE:
                tqdm.write(f"  No base {timeframe} data for {symbol} → skipping cascading timeframes")
            return True

        # Load the saved offsets (or create if not exists)
        input_position, output_position = resample_read_index(index_path)

        # Ensure output file exists
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
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

            eof_reached = False

            while True:

                # Read a StringIO batch from f_input
                sio, eof_reached = resample_batch_read(f_input, header)

                # Resample the sio batch
                resampled, next_input_position = resample_batch(sio, rule, label, closed) 

                # Rewrite the output file from its last known position
                f_output.seek(output_position)

                # Crash rewind/rewrite last (incomplete) candle
                f_output.truncate(output_position)

                # Write all but last candle (fully complete)
                f_output.write(resampled.iloc[:-1].to_csv(index=True, header=False))

                # Flush
                f_output.flush()

                # Update the index (lock completed data in-place immediately)
                resample_write_index(index_path, next_input_position, output_position)

                # Update output position
                output_position = f_output.tell()

                # Write the last candle (will be overwritten on next run)
                f_output.write(resampled.tail(1).to_csv(index=True, header=False))

                # Stop if EOF reached
                if eof_reached:
                    if VERBOSE:
                        tqdm.write(f"  ✓ {symbol} {timeframe}")
                    break

                # Seek to updated offset for next loop
                f_input.seek(next_input_position)


    return True


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
    try:
        resample_symbol(symbol)
    except Exception as e:
        raise
    finally:
        pass
