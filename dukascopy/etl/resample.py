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
import copy 
import os
import pandas as pd
import yaml
from dataclasses import asdict
from config.app_config import AppConfig, ResampleConfig, ResampleSymbolOverride, load_app_config
from pathlib import Path
from tqdm import tqdm
from io import StringIO
from typing import Tuple, IO

VERBOSE = os.getenv('VERBOSE', '0').lower() in ('1', 'true', 'yes', 'on')

def resample_get_symbol_config(symbol: str, app_config: AppConfig) -> ResampleConfig:
    """
    Generate a merged resample configuration for a specific symbol.

    This function starts from the global resample configuration and applies
    any symbol-specific overrides defined in `app_config.symbols`. Overrides
    may include:
        - round_decimals
        - batch_size
        - custom timeframes
        - skipped timeframes (absolute priority)

    Parameters
    ----------
    symbol : str
        The trading symbol for which to generate the configuration (e.g., "BTC-USDT").
    app_config : AppConfig
        The root application configuration containing the global resample
        settings and any symbol-specific overrides.

    Returns
    -------
    ResampleConfig
        A new ResampleConfig instance with global settings merged with
        symbol-specific overrides.
    """
    # Start with global resample configuration
    global_config: ResampleConfig = app_config.resample
    merged_config: ResampleConfig = copy.deepcopy(global_config)

    # Check for symbol-specific overrides
    symbol_override: ResampleSymbolOverride = global_config.symbols.get(symbol)

    if symbol_override:
        # Override global round_decimals if specified
        if symbol_override.round_decimals is not None:
            merged_config.round_decimals = symbol_override.round_decimals

        # Override global batch_size if specified
        if symbol_override.batch_size is not None:
            merged_config.batch_size = symbol_override.batch_size

        # Merge custom timeframes, overriding global ones if needed
        if symbol_override.timeframes:
            merged_config.timeframes.update(symbol_override.timeframes)

        # Remove any skipped timeframes (absolute priority)
        if symbol_override.skip_timeframes:
            for timeframe_key in symbol_override.skip_timeframes:
                merged_config.timeframes.pop(timeframe_key, None)

    return merged_config

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

def resample_batch_read(f_input: IO, header: str, config: ResampleConfig) -> Tuple[StringIO, bool]:
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
    config: ResampleConfig
        Config object

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
    for _ in range(config.batch_size):
        offset_before = f_input.tell()
        line = f_input.readline()
        if not line:
            eof_reached = True
            break
        sio.write(f"{line.strip()},{offset_before}\n")  # offset column injection for traceability
    
    sio.seek(0)

    return sio, eof_reached

def resample_batch(sio: StringIO, rule: str, label: str, closed: str, origin: str, config: ResampleConfig) -> Tuple[pd.DataFrame, int]:
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
    config: ResampleConfig
        Config object

    Returns
    -------
    pd.DataFrame
        A resampled OHLCV DataFrame with:
            - open:   first value in window
            - high:   maximum value in window
            - low:    minimum value in window
            - close:  last value in window
            - volume: sum of volumes in window
        All numeric fields are rounded to `config.round_decimals`.
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
        index_col="time",
        date_format="%Y-%m-%d %H:%M:%S"
    )
    
    # Resample into target timeframe
    resampled = df.resample(rule, label=label, closed=closed, origin=origin).agg({
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
    resampled = resampled.round(config.round_decimals)

    # Filter zero volume
    resampled = resampled[resampled['volume'].notna() & (resampled['volume'] != 0)]

    # Force date-format YYYY-MM-DD HH:MM:SS (might drop time on 1D)
    resampled.index = resampled.index.strftime("%Y-%m-%d %H:%M:%S")

    # Return the resampled dataframe
    return resampled, next_input_position

def resample_symbol(symbol: str, app_config: AppConfig) -> bool:
    """
    Incrementally resample OHLCV data for a single trading symbol across all configured timeframes.

    The function performs a forward-only, crash-resilient resampling pipeline:
        - Loads and merges global and symbol-specific configuration.
        - Reads the input CSV in batches, tracking byte offsets.
        - Resamples each batch into the target timeframe (cascading from lower to higher).
        - Always rewrites the last candle because it may be incomplete.
        - Persists read/write offsets atomically to ensure crash safety.
        - Skips timeframes if input data is missing or skipped in the configuration.

    Notes
    -----
    - Supports append-only incremental input: historical rows are never reprocessed.
    - The last candle of each batch may be overwritten on the next run.
    - Timeframes without a resampling rule are treated as direct input paths.
    - Output files and index files are created automatically if they do not exist.

    Parameters
    ----------
    symbol : str
        The normalized trading symbol to process (e.g., "BTC-USDT").
    config : ResampleConfig
        The resampling configuration object, including global defaults, symbol overrides,
        paths, timeframes, and other options.

    Returns
    -------
    bool
        Always returns True for now. This may be extended in the future for status reporting.
    """
    config = resample_get_symbol_config(symbol, app_config)

    # Main output path
    data_path = config.paths.data

    for _, ident in enumerate(config.timeframes):
        # Get ResampleTimeFrame
        timeframe = config.timeframes.get(ident)

        # Handle case of no rule = direct input path
        if not timeframe.rule:
            if not Path(f"{timeframe.source}/{symbol}.csv").exists():
                raise IOError(f"Invalid configuration for timeframe {ident}")
            continue
        
        # Construct file paths
        if config.timeframes.get(timeframe.source).rule is not None:
            input_path = Path(f"{data_path}/{timeframe.source}/{symbol}.csv")
        else:
            input_path = Path(f"{config.timeframes.get(timeframe.source).source}/{symbol}.csv")

        output_path = Path(f"{data_path}/{ident}/{symbol}.csv")
        index_path = Path(f"{data_path}/{ident}/index/{symbol}.idx")

        rule, label, closed, origin = [timeframe.rule, timeframe.label, timeframe.closed, timeframe.origin]

        # Ensure input path exists
        if not input_path.exists():
            if VERBOSE:
                tqdm.write(f"  No base {ident} data for {symbol} → skipping cascading timeframes")
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
                sio, eof_reached = resample_batch_read(f_input, header, config)

                # Resample the sio batch
                resampled, next_input_position = resample_batch(sio, rule, label, closed, origin, config) 

                # Rewrite the output file from its last known position
                f_output.seek(output_position)

                # Crash rewind/rewrite last (incomplete) candle
                f_output.truncate(output_position)

                # Write all but last candle (fully complete)
                f_output.write(resampled.iloc[:-1].to_csv(index=True, header=False))

                # Flush
                f_output.flush()

                # Update output position
                output_position = f_output.tell()

                # Update the index (lock completed data in-place immediately)
                resample_write_index(index_path, next_input_position, output_position)

                # Write the last candle (will be overwritten on next run)
                f_output.write(resampled.tail(1).to_csv(index=True, header=False))

                # Stop if EOF reached
                if eof_reached:
                    if VERBOSE:
                        tqdm.write(f"  ✓ {symbol} {ident}")
                    break

                # Seek to updated offset for next loop
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
