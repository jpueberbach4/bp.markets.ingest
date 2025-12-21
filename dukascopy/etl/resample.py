#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resample.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Description: Conversion to OOP - Incremental OHLCV resampling engine.

              This module provides two main components:

              - ResampleEngine: Handles incremental, batch-based resampling for
                a single symbol and target timeframe, including index tracking
                for resumable runs.
              - ResampleWorker: Orchestrates resampling across all configured
                timeframes for a given symbol.

              The design supports cascading resampling (e.g. 1m → 5m → 1h),
              session-aware origins, and crash-safe progress tracking via index
              files.
===============================================================================
"""
import os
import pandas as pd
import numpy as np
from pathlib import Path
from io import StringIO
from typing import Tuple, IO, Optional
from tqdm import tqdm

from config.app_config import AppConfig, ResampleSymbol, resample_get_symbol_config, load_app_config, ResampleTimeframeProcessingStep
from helper import ResampleTracker

from dataclasses import asdict
import yaml

# Enable verbose logging via environment variable
VERBOSE = os.getenv("VERBOSE", "0").lower() in ("1", "true", "yes", "on")


class ResampleEngine:
    """
    Incremental OHLCV resampling engine for a single symbol and timeframe.

    This class encapsulates:
    - Path resolution for input, output, and index files
    - Crash-safe index tracking for resumable processing
    - Batch-based reading of source data
    - Session-aware pandas resampling
    """

    def __init__(
        self,
        symbol: str,
        ident: str,
        config: ResampleSymbol,
        data_path: Path,
    ):
        """
        Initializes the resampling engine.

        Args:
            symbol (str): Trading symbol (e.g. "BTCUSDT").
            ident (str): Target timeframe identifier (e.g. "5m", "1h").
            config (ResampleSymbol): Symbol-specific resampling configuration.
            data_path (Path): Base directory for derived timeframe data.
        """
        self.symbol = symbol
        self.ident = ident
        self.config = config

        # Tracker resolves active session and origin timestamps
        self.tracker = ResampleTracker(config)

        # Root directory for resampled CSVs
        self.data_path = data_path

        # These are resolved dynamically based on timeframe configuration
        self.input_path: Optional[Path] = None
        self.output_path: Optional[Path] = None
        self.index_path: Optional[Path] = None

        # True when timeframe is a root source (no resampling required)
        self.is_root: bool = False

        # Resolve all filesystem paths immediately
        self._resolve_paths()

    def _resolve_paths(self) -> None:
        """
        Resolves input, output, and index paths for the configured timeframe.

        This method:
        - Detects root vs derived timeframes
        - Resolves upstream source dependencies
        - Validates required input files
        - Ensures output directories/files exist

        Raises:
            IOError: If a required root CSV is missing.
            ValueError: If a timeframe dependency is invalid or missing.
        """
        timeframe = self.config.timeframes.get(self.ident)

        # ------------------------------------------------------------------
        # Root timeframe: pass-through source (e.g. 1m CSV)
        # ------------------------------------------------------------------
        if not timeframe.rule:
            root_source = Path(timeframe.source) / f"{self.symbol}.csv"

            # Root CSV must exist
            if not root_source.exists():
                raise IOError(f"Root source missing for {self.ident}: {root_source}")

            self.input_path = None
            self.output_path = root_source
            self.index_path = Path()
            self.is_root = True
            return

        # ------------------------------------------------------------------
        # Derived timeframe: resampled from another timeframe
        # ------------------------------------------------------------------
        source_tf = self.config.timeframes.get(timeframe.source)
        if not source_tf:
            raise ValueError(
                f"Timeframe {self.ident} references unknown source: {timeframe.source}"
            )

        # Resolve upstream input path
        if source_tf.rule is not None:
            # Source itself is resampled
            input_path = self.data_path / timeframe.source / f"{self.symbol}.csv"
        else:
            # Source is an external CSV
            input_path = Path(source_tf.source) / f"{self.symbol}.csv"

        # Output CSV and index file locations
        output_path = self.data_path / self.ident / f"{self.symbol}.csv"
        index_path = self.data_path / self.ident / "index" / f"{self.symbol}.idx"

        # Validate that upstream data exists
        if not input_path.exists():
            if VERBOSE:
                tqdm.write(f"  No base {self.ident} data for {self.symbol} → skipping")
            raise ValueError(f"No base data for {self.symbol} at {self.ident}")

        # Ensure output directory and file exist
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.touch()

        self.input_path = input_path
        self.output_path = output_path
        self.index_path = index_path
        self.is_root = False

    def _apply_post_processing(self, df: pd.DataFrame, step: ResampleTimeframeProcessingStep) -> pd.DataFrame:
        if step.action != "merge":
            raise ValueError(f"Unsupported post-processing action {step.action}")
        
        # TODO: implement from_date and to_date
        #       generate a mask where from_date <= date <= to_date
        #       then use mask as primary filter and endswith as secondary filter
        #       gives a positions array, continue regular logic 
        
        offset = step.offset
        for ends_with in step.ends_with:
            positions = np.where(df.index.str.endswith(ends_with))[0]

            for pos in positions:
                # Ensure there is a row before the selects to merge into
                if pos > 0:
                    select_idx = df.index[pos]
                    anchor_idx = df.index[pos + offset]
                    df.at[anchor_idx, 'high'] = max(df.at[anchor_idx, 'high'], df.at[select_idx, 'high'])
                    df.at[anchor_idx, 'low'] = min(df.at[anchor_idx, 'low'], df.at[select_idx, 'low'])
                    df.at[anchor_idx, 'close'] = df.at[select_idx, 'close']
                    df.at[anchor_idx, 'volume'] += df.at[select_idx, 'volume']

            # drop all select sources
            df = df[~df.index.str.endswith(ends_with)]

        return df

    def read_index(self) -> Tuple[int, int]:
        """
        Reads persisted input/output byte offsets from the index file.

        If the index file does not exist, it is created and initialized.

        Returns:
            Tuple[int, int]:
                - input_pos: Byte offset in the input file.
                - output_pos: Byte offset in the output file.
        """
        # Initialize index if missing
        if not self.index_path or not self.index_path.exists():
            self.write_index(0, 0)
            return 0, 0

        # Read the first two lines (input_pos, output_pos)
        with open(self.index_path, "r") as f:
            lines = f.readlines()[:2]

        if len(lines) == 2:
            return int(lines[0].strip()), int(lines[1].strip())

        # Fallback if index file is malformed
        return 0, 0

    def write_index(self, input_pos: int, output_pos: int) -> None:
        """
        Atomically writes updated input/output offsets to disk.

        Uses a temporary file and `os.replace` to guarantee crash safety.

        Args:
            input_pos (int): Byte offset in the input file.
            output_pos (int): Byte offset in the output file.
        """
        # Ensure index directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Write offsets to a temporary file
        temp_path = self.index_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            f.write(f"{input_pos}\n{output_pos}")
            f.flush()

        # Atomic replace
        os.replace(temp_path, self.index_path)

    def prepare_batch(self, f_input: IO, header: str) -> Tuple[StringIO, bool]:
        """
        Reads a batch of rows from the input CSV and enriches them with metadata.

        Each row is extended with:
        - origin: Session-aware resampling origin timestamp
        - offset: Byte offset before the row was read

        Args:
            f_input (IO): Open input CSV file handle.
            header (str): Original CSV header line.

        Returns:
            Tuple[StringIO, bool]:
                - StringIO buffer containing the enriched CSV batch.
                - eof flag indicating whether end-of-file was reached.
        """
        # Initialize in-memory buffer for the output batch
        sio = StringIO()

        # Write CSV header with appended metadata columns
        sio.write(f"{header.strip()},origin,offset\n")

        # Track end-of-file state and last processed session/day key
        eof = False
        last_key = None

        # Check whether the tracker is running in single-session mode
        is_default = self.tracker.is_default_session()

        # Precompute origin for the single-session (default) case
        primary_session = next(iter(self.config.sessions.values()))
        default_origin = primary_session.timeframes[self.ident].origin

        # Read up to batch_size rows from the input file
        for _ in range(self.config.batch_size):
            # Capture byte offset before reading the row
            offset_before = f_input.tell()
            line = f_input.readline()

            # Stop processing if end-of-file is reached
            if not line:
                eof = True
                break

            # Resolve origin dynamically when multiple sessions are configured
            if not is_default:
                try:
                    # Determine the active session for the current row
                    session = self.tracker.get_active_session(line)
                    current_key = f"{session}/{line[:10]}"  # session + date prefix

                    # Recompute origin only when session or day changes
                    if current_key != last_key:
                        origin = self.tracker.get_active_origin(
                            line, self.ident, session
                        )
                        last_key = current_key
                except Exception as e:
                    # Propagate errors encountered during session/origin resolution
                    raise e
            else:
                # Use precomputed origin for single-session mode
                origin = default_origin

            # Write the enriched CSV row to the output buffer
            sio.write(f"{line.strip()},{origin},{offset_before}\n")

        # Reset buffer cursor for downstream consumers
        sio.seek(0)
        return sio, eof


    def process_resample(self, sio: StringIO) -> Tuple[pd.DataFrame, int]:
        """
        Resamples a prepared batch into the target timeframe.

        Data is grouped by origin and resampled independently to ensure
        correct session boundaries.

        Args:
            sio (StringIO): Batch buffer produced by `prepare_batch`.

        Returns:
            Tuple[pandas.DataFrame, int]:
                - Resampled OHLCV DataFrame.
                - Byte offset for resuming the next batch.

        Raises:
            ValueError: If the batch contains no data.
        """
        # Load the prepared CSV batch into a DataFrame indexed by timestamp
        df = pd.read_csv(
            sio,
            parse_dates=["time"],
            index_col="time",
            date_format="%Y-%m-%d %H:%M:%S",
        )

        # Guard against empty batches
        if df.empty:
            raise ValueError("Empty batch read from StringIO")

        # Accumulate per-origin resampled DataFrames
        resampled_list = []

        # Retrieve timeframe configuration from the primary session
        session = next(iter(self.config.sessions.values()))
        tf_cfg = session.timeframes[self.ident]

        # Resample each origin independently to preserve session boundaries
        for origin, origin_df in df.groupby("origin"):
            res = origin_df.resample(
                tf_cfg.rule,              # Resampling rule (e.g., '5T', '1H')
                label=tf_cfg.label,       # Label alignment for resampled bars
                closed=tf_cfg.closed,     # Interval closure (left/right)
                origin=origin,            # Session-aware origin timestamp
            ).agg(
                {
                    "open": "first",      # First price in the interval
                    "high": "max",        # Highest price in the interval
                    "low": "min",         # Lowest price in the interval
                    "close": "last",      # Last price in the interval
                    "volume": "sum",      # Total traded volume
                    "offset": "first",    # Byte offset for resume tracking
                }
            )

            # Drop empty or invalid bars (e.g., no volume)
            res = res[res["volume"].gt(0) & res["volume"].notna()]
            resampled_list.append(res)

        # Combine all resampled origins into a single, time-sorted DataFrame
        full_resampled = pd.concat(resampled_list).sort_index()

        # Normalize index formatting for downstream consumers
        full_resampled.index = full_resampled.index.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Apply post-processing (currently ugly, improve in future)
        if tf_cfg.post:
            for tf_step in tf_cfg.post.values():
                full_resampled = self._apply_post_processing(full_resampled, tf_step)

        # Determine the resume position from the last completed bar
        next_input_pos = int(full_resampled.iloc[-1]["offset"])

        # Remove internal metadata and apply final rounding
        full_resampled = (
            full_resampled.drop(columns=["offset"])
            .round(self.config.round_decimals)
        )

        return full_resampled, next_input_pos


class ResampleWorker:
    """
    Coordinates resampling across all configured timeframes for a symbol.
    """

    def __init__(self, symbol: str, app_config: AppConfig):
        """
        Initializes a resampling worker.

        Args:
            symbol (str): Trading symbol to process.
            app_config (AppConfig): Global application configuration.
        """
        self.symbol = symbol
        self.app_config = app_config

        # Load symbol-specific resampling configuration
        self.config = resample_get_symbol_config(symbol, app_config)

        # Root directory for resampled data
        self.data_path = Path(app_config.resample.paths.data)

    def run(self) -> None:
        """
        Executes resampling sequentially for all configured timeframes.

        Cascading dependencies are respected: if a lower timeframe fails,
        higher derived timeframes are skipped.
        """
        for ident in self.config.timeframes:
            try:
                # 1. Initialize engine (path resolution happens here)
                engine = ResampleEngine(self.symbol, ident, self.config, self.data_path)

                # 2. Skip root timeframes (sources only)
                if engine.is_root:
                    continue

                # 3. Execute incremental resampling
                self._execute_engine(engine)

            except (ValueError, IOError) as e:
                if VERBOSE:
                    tqdm.write(f"  ! Skipping {ident} for {self.symbol}: {e}")
                # Break cascade: higher TFs depend on this one
                break

    def _execute_engine(self, engine: ResampleEngine) -> None:
        """
        Runs the incremental resampling loop for a single timeframe.

        This method:
        - Restores progress from index files
        - Processes data in batches
        - Writes completed bars safely
        - Persists progress after each batch

        Args:
            engine (ResampleEngine): Initialized resampling engine.
        """
        # Restore last known read/write positions from index files
        input_pos, output_pos = engine.read_index()

        # Open input CSV for reading and output CSV for read/write updates
        with open(engine.input_path, "r") as f_in, open(engine.output_path, "r+") as f_out:
            # Read and cache the input CSV header
            header = f_in.readline()

            # Resume input reading from the last processed byte offset
            if input_pos > 0:
                f_in.seek(input_pos)

            # If starting from a fresh output file, write the CSV header
            if output_pos == 0:
                f_out.write(header)
                output_pos = f_out.tell()

            # Process input data incrementally until EOF is reached
            while True:
                # Read the next batch and enrich it with metadata
                sio, eof = engine.prepare_batch(f_in, header)
                try:
                    # Resample the batch and compute the next input position
                    resampled, next_in_pos = engine.process_resample(sio)
                finally:
                    # Ensure the in-memory buffer is always released
                    sio.close()

                # Roll back output file to the last confirmed safe position
                f_out.seek(output_pos)
                f_out.truncate(output_pos)

                # Write all fully completed bars (exclude trailing partial bar)
                f_out.write(resampled.iloc[:-1].to_csv(index=True, header=False))
                f_out.flush()

                # Persist progress after writing confirmed bars
                output_pos = f_out.tell()
                engine.write_index(next_in_pos, output_pos)

                # Write the trailing bar, which may be updated in the next batch
                f_out.write(resampled.tail(1).to_csv(index=True, header=False))

                # Exit the loop once the input file has been fully consumed
                if eof:
                    break

                # Resume reading input from the computed byte offset
                f_in.seek(next_in_pos)



def fork_resample(args) -> bool:
    """
    Multiprocessing-friendly entry point for symbol resampling.

    Args:
        args (Tuple[str, AppConfig]): Tuple containing:
            - symbol: Trading symbol.
            - app_config: Global application configuration.

    Returns:
        bool: True if resampling completed successfully.
    """
    symbol, config = args
    worker = ResampleWorker(symbol, config)
    worker.run()
    return True



if __name__ == "__main__":
    # Load YAML config (currently only resample support)
    app_config = load_app_config('config.user.yaml')

    # CONFIG IS FUN!!
    symbol_config = resample_get_symbol_config("SGD.IDX-SGD", app_config)

    session = next(iter(symbol_config.sessions.values()))
    tf_cfg = session.timeframes["4h"]

    print(yaml.safe_dump(
        asdict(symbol_config),
        default_flow_style=False,
        sort_keys=False,
    ))

    os.exit

    fork_resample(["AUS.IDX-AUD",config])
