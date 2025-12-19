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

     NOTE: timestamps are already normalized in transform.py (UTC-relative).

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
import copy 
import os
import pandas as pd
import yaml

from config.app_config import AppConfig, ResampleConfig, ResampleSymbol, load_app_config, resample_get_symbol_config
from pathlib import Path
from tqdm import tqdm
from io import StringIO
from typing import Tuple, IO, Optional
from dataclasses import asdict
from helper import resample_resolve_paths, ResampleTracker

from config.app_config import AppConfig, load_app_config # remove later


VERBOSE = os.getenv('VERBOSE', '0').lower() in ('1', 'true', 'yes', 'on')



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
            raise IOError(f"Index file {index_path} corrupted or incomplete.")
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

def resample_batch_read(f_input: IO, header: str, config: ResampleSymbol, symbol: str, ident: str) -> Tuple[StringIO, bool]:
    """
    Read a batch of lines from the input CSV, appending origin and byte offset.

    This function reads up to `config.batch_size` lines from the input file,
    determines the active session and origin for each row, and writes the result
    into a StringIO buffer along with the byte offset of each input line. It 
    supports both default sessions (single origin) and multiple trading sessions.

    Parameters
    ----------
    f_input : IO
        Input file-like object to read raw CSV lines from.
    header : str
        CSV header line to include in the output StringIO.
    config : ResampleSymbol
        Configuration for the symbol including session and timeframe information.
    symbol : str
        Trading symbol identifier.
    ident : str
        Timeframe identifier.

    Returns
    -------
    Tuple[StringIO, bool]
        - StringIO containing the batch with appended 'origin' and 'offset' columns.
        - EOF flag (True if end of input file reached during this batch).
    """
    sio = StringIO()
    # Write header including origin and offset columns
    sio.write(f"{header.strip()},origin,offset\n")

    eof_reached = False  # Flag to track if end of input is reached
    last_key = None      # Cache key to avoid redundant origin calculations

    tracker = ResampleTracker(config)
    # Check if symbol has only a default session
    is_default_session = tracker.is_default_session(config)

    # Read up to batch_size lines from input
    for _ in range(config.batch_size):
        offset_before = f_input.tell()  # Save current byte offset
        line = f_input.readline()       # Read one line from input
        if not line:
            eof_reached = True
            break

        if not is_default_session:
            # Determine the active session for this line
            session = tracker.get_active_session(line)
            # Cache key to detect session/date changes
            current_key = f"{session}/{line[:10]}"
            if current_key != last_key:
                # Update origin only if session or date changed
                origin = tracker.get_active_origin(line, ident, session, config)
                last_key = current_key
        else:
            # For default session, origin is static
            origin = config.sessions.get("default").timeframes.get(ident).origin

        # Write the line with origin and input byte offset for traceability
        sio.write(f"{line.strip()},{origin},{offset_before}\n")

    # Rewind StringIO to the beginning for downstream reading
    sio.seek(0)
    return sio, eof_reached


def resample_batch(sio: StringIO, ident, config: ResampleSymbol) -> Tuple[pd.DataFrame, int]:
    """
    Resample a batch of OHLCV rows for a given symbol and timeframe.

    Reads a batch of input rows from a StringIO object, splits them by 'origin',
    resamples each origin separately using the configured rules, and combines the 
    results into a single DataFrame. Returns the resampled DataFrame and the 
    byte offset of the last input row used.

    Parameters
    ----------
    sio : StringIO
        StringIO buffer containing the batch of CSV input rows, including
        'origin' and 'offset' columns.
    ident : str
        Timeframe identifier for the target resampling (e.g., "5m", "1h").
    config : ResampleSymbol
        Symbol configuration object containing session and timeframe rules.

    Returns
    -------
    Tuple[pd.DataFrame, int]
        - Resampled DataFrame with OHLCV values and datetime index.
        - Byte offset of the last input row used, to update the index file.
    """
    # Load batch into a DataFrame with time as index
    df = pd.read_csv(
        sio,
        header=0,
        parse_dates=["time"],
        index_col="time",
        date_format="%Y-%m-%d %H:%M:%S"
    )

    # Store resampled data for each origin
    resampled_list = []

    # Identify all unique origin values in this batch
    origins = df['origin'].unique().tolist()

    for origin in origins:
        # Use the first session's timeframe to get the resampling rules
        # Since sessions can grow large, we stick to next-iter
        _, session = next(iter(config.sessions.items()))
        timeframe = session.timeframes.get(ident)
        rule, label, closed = [timeframe.rule, timeframe.label, timeframe.closed]

        # Filter rows for this origin and drop the 'origin' column
        # NOTE: This can now be parellized, each thread an origin
        origin_df = df[df['origin'] == origin].copy()
        origin_df.drop(columns=["origin"], inplace=True)

        # Resample the origin-specific DataFrame
        origin_resampled = origin_df.resample(
            rule, label=label, closed=closed, origin=origin
        ).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'offset': 'first'  # capture the input offset of first row in window
        })

        # Remove gaps: rows with zero or NaN volume
        origin_resampled = origin_resampled[
            origin_resampled['volume'].notna() & (origin_resampled['volume'] != 0)
        ]

        # Append the resampled DataFrame to the list
        resampled_list.append(origin_resampled)

    # Combine all origins into a single DataFrame and sort by time
    resampled = pd.concat(resampled_list).sort_index()

    # Ensure we have data; otherwise, raise an error
    if resampled.empty:
        raise ValueError("Resampled result for sessions were empty. This is impossible behavior.")

    # Capture the input byte offset for the last row processed
    next_input_position = int(resampled.iloc[-1]['offset'])

    # Remove the temporary 'offset' column
    resampled.drop(columns=["offset"], inplace=True)

    # Round numerical values to avoid floating-point drift
    resampled = resampled.round(config.round_decimals)

    # Filter any remaining rows with zero or NaN volume
    resampled = resampled[resampled['volume'].notna() & (resampled['volume'] != 0)]

    # Ensure index is formatted as YYYY-MM-DD HH:MM:SS
    resampled.index = resampled.index.strftime("%Y-%m-%d %H:%M:%S")

    return resampled, next_input_position


def resample_symbol(symbol: str, app_config: AppConfig) -> bool:
    """
    Incrementally resample OHLCV data for a single trading symbol across all configured timeframes.

    The function performs a forward-only, crash-resilient resampling pipeline:
        - Loads symbol-specific configuration.
        - Reads the input CSV in batches, tracking byte offsets.
        - Resamples each batch into the target timeframe.
        - Rewrites the last candle to ensure completeness.
        - Persists read/write offsets atomically to ensure crash safety.
        - Skips timeframes if input data is missing.

    Parameters
    ----------
    symbol : str
        Trading symbol identifier (e.g., "BTC-USDT").
    app_config : AppConfig
        The application configuration containing global and per-symbol settings.

    Returns
    -------
    bool
        Always returns True to indicate successful resampling.
    """
    # Determine the base path for resampled data
    data_path = Path(app_config.resample.paths.data)

    # Get the merged ResampleSymbol configuration for the symbol
    config = resample_get_symbol_config(symbol, app_config)

    for _, ident in enumerate(config.timeframes):
        # Resolve input/output/index paths for this timeframe
        input_path, output_path, index_path, skip = resample_resolve_paths(symbol, ident, data_path, config)
        if skip:
            continue

        # Read saved offsets or create default if index missing
        input_position, output_position = resample_read_index(index_path)
        with open(input_path, "r") as f_input, open(output_path, "r+") as f_output:
            # Read header line from input
            header = f_input.readline()

            # Seek to last processed position in input
            if input_position > 0:
                f_input.seek(input_position)

            # Initialize output file with header if new
            if output_position == 0:
                f_output.write(header)
                output_position = f_output.tell()

            eof_reached = False

            while True:
                # Read a batch from input and annotate with origin and offset
                sio, eof_reached = resample_batch_read(f_input, header, config, symbol, ident)

                # Resample the batch into the target timeframe
                resampled, next_input_position = resample_batch(sio, ident, config) 

                # Seek to the last known output position
                f_output.seek(output_position)

                # Crash-safe rewrite: truncate to last committed position
                f_output.truncate(output_position)

                # Write all fully complete candles
                f_output.write(resampled.iloc[:-1].to_csv(index=True, header=False))
                f_output.flush()

                # Update output position and index file
                output_position = f_output.tell()
                resample_write_index(index_path, next_input_position, output_position)

                # Write the last (potentially incomplete) candle
                f_output.write(resampled.tail(1).to_csv(index=True, header=False))

                # Stop if end-of-file reached
                if eof_reached:
                    if VERBOSE:
                        tqdm.write(f"  ✓ {symbol} {ident}")
                    break

                # Seek to next input offset for next batch
                f_input.seek(next_input_position)

    return True



def fork_resample(args) -> bool:
    """
    Process all dates for a single symbol sequentially.

    Intended for use with multiprocessing where each worker handles
    one symbol over the full date range.

    Parameters
    ----------
    args : tuple
        Tuple containing (symbol, list of dates, config).
    """
    symbol, config = args
    
    resample_symbol(symbol, config)

    return True
