#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resample.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Updated:     2026-01-07
              Full refactor and documentation update:
              - Optional fsync for I/O durability
              - Custom exceptions for traceable failures
              - Vectorized session-aware pre- and post-processing
              - Incremental, crash-safe read–process–write loop
              - Batch resampling with held-back last bar for continuity
              - Abstracted IO

 Description: Object-oriented, crash-safe OHLCV resampling engine with session,
 DST, and incremental processing awareness.

              This module implements a robust, incremental resampling pipeline
              for high-frequency OHLCV data. It transforms base timeframes
              (e.g., 1m) into derived timeframes (e.g., 5m, 1h) while ensuring:

                - Session-aware bar generation
                - DST-aware origin handling
                - Incremental batch processing with resume support
                - Idempotent recovery after partial failures
                - Explicit dependency ordering between timeframes
                - Transactional write logic to prevent partial output corruption

              Core classes:
                - ResampleEngine: Handles resampling for a single symbol and
                  timeframe, with full pre- and post-processing.
                - ResampleWorker: Orchestrates resampling across all configured
                  timeframes for a symbol.
              
              Features:
                - Vectorized session pre-processing
                - Post-processing for merging and shifting intermediate bars
                - Crash-safe index persistence for input/output offsets
                - Optional fsync for guaranteed I/O durability
                - Incremental, batch-based processing with fail-fast behavior
                - Multiprocessing-friendly forkable worker

 Usage:
     - Imported and executed by a resampling scheduler or run per symbol.
     - Supports multiprocessing/forking via the `fork_resample` helper.
     - Can recover and resume after partial failures without data loss.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - pytz

 License:
     MIT License
===============================================================================
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from io import StringIO
from typing import Tuple, IO, Optional

from etl.config.app_config import AppConfig, ResampleSymbol, resample_get_symbol_config, ResampleTimeframeProcessingStep
from etl.processors.resample_pre_process import resample_pre_process_origin
from etl.processors.resample_post_process import resample_post_process_merge, resample_post_process_shift


from etl.io.protocols import *
from etl.exceptions import *
from etl.io.resample.factory import *

import traceback


class ResampleEngine:

    def __init__(
        self,
        symbol: str,
        ident: str,
        config: ResampleSymbol,
        data_path: Path,
    ):
        """Initialize the resample I/O manager for a symbol and timeframe.

        This initializer configures the I/O mode, resolves all filesystem paths,
        and sets up the appropriate reader, writer, and index handlers based on
        the provided resampling configuration. If the timeframe represents a
        root source (i.e., no resampling is required), I/O initialization is
        skipped.

        Args:
            symbol (str): Trading symbol (e.g., "BTC-USD").
            ident (str): Unique identifier for the resample instance, typically
                derived from timeframe or configuration.
            config (ResampleSymbol): Resampling configuration, including timeframe,
                file mode, and synchronization options.
            data_path (Path): Root directory where resampled data and indexes
                are stored.

        Attributes:
            fmode: Primary I/O mode (e.g., binary or text).
            symbol: Trading symbol associated with this resampler.
            ident: Unique identifier for this resample configuration.
            config: Resampling configuration object.
            data_path: Root directory for resampled data.
            reader: Reader instance for input data, if applicable.
            writer: Writer instance for output data, if applicable.
            index: Index reader/writer for tracking resampled records.
            input_path: Resolved path to input data.
            output_path: Resolved path to output data.
            index_path: Resolved path to index data.
            is_root: Whether the timeframe is a root source that does not require
                resampling.
        """
        # Set primary IO mode
        self.fmode = config.fmode

        # Set properties
        self.symbol = symbol
        self.ident = ident
        self.config = config

        # Root directory for resampled CSVs
        self.data_path = data_path

        # Declare IO
        self.reader: Optional[ResampleIOReader] = None
        self.writer: Optional[ResampleIOWriter] = None
        self.index: Optional[ResampleIOIndexReaderWriter] = None

        # These are resolved dynamically based on timeframe configuration
        self.input_path: Optional[Path] = None
        self.output_path: Optional[Path] = None
        self.index_path: Optional[Path] = None

        # True when timeframe is a root source (no resampling required)
        self.is_root: bool = False

        # Resolve all filesystem paths immediately
        self._resolve_paths()

        # Skip setting up IO if root timeframe (eg 1m)
        if self.is_root:
            return

        # Initialize IO
        self.index = ResampleIOFactory.get_index_handler(self.index_path, self.fmode, fsync=self.config.fsync)
        self.reader = ResampleIOFactory.get_reader(self.input_path, self.fmode)
        self.writer =  ResampleIOFactory.get_writer(self.output_path, self.fmode, fsync=self.config.fsync)
       


    def _resolve_paths(self) -> None:
        """Resolve and validate all filesystem paths for resampling I/O.

        This method determines the correct input, output, and index paths based
        on the current timeframe configuration and file mode (text or binary).
        It distinguishes between root timeframes, which act as pass-through
        sources, and derived timeframes, which are produced by resampling
        upstream data.

        For root timeframes, no resampling is required and I/O initialization
        is skipped. For derived timeframes, all upstream dependencies are
        validated to ensure required source data exists before resampling.

        Raises:
            DataNotFoundError: If the required root source or upstream dependency
                does not exist on disk.
            ValueError: If the timeframe configuration references an unknown
                source timeframe.
        """
        extension = "csv" if self.fmode == "text" else "bin"
        timeframe = self.config.timeframes.get(self.ident)

        # Root timeframe: pass-through source (e.g. 1m CSV)
        if not timeframe.rule:
            root_source = Path(timeframe.source) / f"{self.symbol}.{extension}"

            # Root CSV must exist
            if not root_source.exists():
                raise DataNotFoundError(f"Missing root source for {self.symbol} at {root_source}")

            # Set properties
            self.input_path = None
            self.output_path = root_source
            self.index_path = Path()
            self.is_root = True
            return

        # Derived timeframe: resampled from another timeframe
        source_tf = self.config.timeframes.get(timeframe.source)
        if not source_tf:
            raise ValueError(
                f"Timeframe {self.ident} references unknown source: {timeframe.source}"
            )

        # Resolve upstream input path
        if source_tf.rule is not None:
            # Source itself is resampled
            input_path = self.data_path / timeframe.source / f"{self.symbol}.{extension}"
        else:
            # Source is an external CSV
            input_path = Path(source_tf.source) / f"{self.symbol}.{extension}"

        # Output CSV and index file locations
        output_path = self.data_path / self.ident / f"{self.symbol}.{extension}"
        index_path = self.data_path / self.ident / "index" / f"{self.symbol}.idx"

        # Validate that upstream data exists
        if not input_path.exists():
            raise DataNotFoundError(f"Dependency missing: {self.symbol} needs {timeframe.source} first.")

        # Update properties
        self.input_path = input_path
        self.output_path = output_path
        self.index_path = index_path
        self.is_root = False

    def _apply_pre_processing(self, df: pd.DataFrame, step: ResampleTimeframeProcessingStep) -> pd.DataFrame:
        """Apply a single pre-processing step to a resampling DataFrame.

        This method executes a configured pre-processing action on the input
        DataFrame prior to resampling. Currently, only the ``origin`` action
        is supported, which delegates to a specialized and potentially complex
        preprocessing routine. Unknown actions are ignored with a warning.

        Args:
            df (pd.DataFrame): Input DataFrame containing time-series data to be
                pre-processed.
            step (ResampleTimeframeProcessingStep): Processing step definition,
                including the action type and its configuration.

        Returns:
            pd.DataFrame: The DataFrame after the pre-processing step has been
            applied. If the action is unknown, the original DataFrame is returned.
        """
        if step.action == "origin":
            # This is a very complicated routine being called
            df = resample_pre_process_origin(df, self.ident, step, self.config)
        else:
            print(f"Warning: unknown pre-process step {step.action}")

        return df

    def _apply_post_processing(
        self,
        df: pd.DataFrame,
        step: ResampleTimeframeProcessingStep
    ) -> pd.DataFrame:
        """Apply a single post-processing step to a resampled DataFrame.

        This method executes a configured post-processing action after the
        resampling step has completed. Supported actions include merging
        derived data and shifting records in time. Any unknown actions are
        ignored with a warning.

        Args:
            df (pd.DataFrame): Resampled DataFrame to be post-processed.
            step (ResampleTimeframeProcessingStep): Processing step definition,
                including the action type and its configuration.

        Returns:
            pd.DataFrame: The DataFrame after the post-processing step has been
            applied. If the action is unknown, the original DataFrame is returned.
        """
        if step.action == "merge":
            df = resample_post_process_merge(df, self.ident, step, self.config)
        elif step.action == "shift":
            df = resample_post_process_shift(df, self.ident, step, self.config)
        else:
            print(f"Warning: unknown post-process step {step.action}")

        return df

    def process_resample(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Resample a batch of time-series data into the configured timeframe.

        This method applies a full resampling pipeline to the input DataFrame,
        including validation, pre-processing, session-aware resampling,
        post-processing, and final data integrity checks. Resampling is performed
        independently per session origin to preserve trading-session boundaries.

        The returned offset enables incremental processing by indicating the
        last fully processed input position.

        Args:
            df (pd.DataFrame): Input time-series data indexed by timestamp.
                The index must be a datetime type and the DataFrame must contain
                all required columns for resampling (e.g., OHLCV, origin, offset).

        Returns:
            Tuple[pd.DataFrame, int]:
                - pd.DataFrame: The fully resampled and post-processed data,
                indexed by the target timeframe.
                - int: The next input offset position used for resume or
                incremental processing.

        Raises:
            ProcessingError: If input validation fails, data integrity checks
                fail, or an unexpected error occurs during processing.
            EmptyBatchError: If resampling produces no output bars.
            ResampleLogicError: If critical resampling invariants are violated
                (e.g., missing offset column or invalid post-processing result).
        """
        try:
            # Validate that the DataFrame index is a datetime type
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                raise ProcessingError(
                    f"Timestamp parsing failed for {self.symbol}: Index is not datetime."
                )

            # Guard against empty input batches
            if df.empty:
                raise ValueError("Empty batch read from StringIO")

            # Accumulate resampled outputs per origin/session
            resampled_list = []

            # Retrieve timeframe configuration (assumes consistent config across sessions)
            session = next(iter(self.config.sessions.values()))
            tf_cfg = session.timeframes[self.ident]

            # Always apply the implicit origin pre-processing step first
            df = self._apply_pre_processing(
                df, ResampleTimeframeProcessingStep(action="origin")
            )

            # Apply any configured pre-processing steps per session
            for name, session in self.config.sessions.items():
                tf_pre = session.timeframes.get(self.ident).pre
                if tf_pre:
                    for name, tf_step in tf_pre.items():
                        df = self._apply_pre_processing(df, tf_step)

            # Resample independently per origin to preserve session boundaries
            for origin, origin_df in df.groupby("origin"):
                res = origin_df.resample(
                    tf_cfg.rule,          # Resampling rule (e.g., '5T', '1H')
                    label=tf_cfg.label,   # Label alignment for resampled bars
                    closed=tf_cfg.closed, # Interval closure (left/right)
                    origin=origin,        # Session-aware origin timestamp
                ).agg(
                    {
                        "open": "first",   # First price in interval
                        "high": "max",     # Highest price in interval
                        "low": "min",      # Lowest price in interval
                        "close": "last",   # Last price in interval
                        "volume": "sum",   # Total traded volume
                        "offset": "first", # Byte offset for resume tracking
                    }
                )

                # Drop empty or invalid bars (no volume)
                res = res[res["volume"].gt(0) & res["volume"].notna()]

                # Collect non-empty resampling results
                if not res.empty:
                    resampled_list.append(res)

            # Ensure at least one bar was produced
            if not resampled_list:
                raise EmptyBatchError(
                    f"Resampling resulted in 0 bars for {self.symbol}."
                )

            # Combine all origins and enforce chronological order
            full_resampled = pd.concat(resampled_list).sort_index()

            # Offset column is critical for resume logic and must be preserved
            if "offset" not in full_resampled.columns:
                raise ResampleLogicError(
                    f"Critical: 'offset' column lost during resampling for {self.symbol}."
                )

            # Apply any configured post-processing steps per session
            for name, session in self.config.sessions.items():
                tf_post = session.timeframes.get(self.ident).post
                if tf_post:
                    for name, tf_step in tf_post.items():
                        full_resampled = self._apply_post_processing(
                            full_resampled, tf_step
                        )

            # Determine the next input offset for incremental processing
            try:
                next_input_pos = int(full_resampled.iloc[-1]["offset"])
            except (IndexError, ValueError, KeyError) as e:
                raise ResampleLogicError(
                    f"Post-processing left no bars for {self.symbol}"
                ) from e

            # Remove internal bookkeeping columns and normalize precision
            full_resampled = (
                full_resampled.drop(columns=["offset"])
                .round(self.config.round_decimals)
            )

            # Final data integrity check
            if full_resampled.isnull().values.any():
                raise ProcessingError(
                    f"Data Error: Result contains NaNs for {self.symbol}"
                )

            return full_resampled, next_input_pos

        except (EmptyBatchError, ResampleLogicError, ProcessingError):
            # Re-raise known, intentional control-flow exceptions
            raise
        except Exception as e:
            # Fail fast: wrap unexpected errors to trigger worker crash logic
            raise ProcessingError(f"Fail-Fast triggered: {e}") from e


class ResampleWorker:
    """
    Coordinates resampling across all configured timeframes for a symbol.
    """

    def __init__(self, symbol: str, app_config: AppConfig):
        """Initialize the resampling context for a specific trading symbol.

        This initializer binds the symbol to the global application configuration,
        loads the symbol-specific resampling configuration, and resolves the root
        filesystem path used for storing resampled data.

        Args:
            symbol (str): Trading symbol to be processed (e.g., "BTCUSDT").
            app_config (AppConfig): Global application configuration containing
                resampling, I/O, and path settings.

        Attributes:
            symbol: Trading symbol associated with this resampling context.
            app_config: Global application configuration instance.
            config: Symbol-specific resampling configuration derived from the
                application settings.
            data_path: Root directory where resampled data for this symbol
        """
        # Set properties
        self.symbol = symbol
        self.app_config = app_config

        # Load symbol-specific resampling configuration
        self.config = resample_get_symbol_config(symbol, app_config)

        # Root directory for resampled data
        self.data_path = Path(app_config.resample.paths.data)

    def run(self) -> None:
        """Execute the resampling pipeline for all configured timeframes.

        This method iterates over all timeframe identifiers defined in the
        symbol’s resampling configuration, initializes a resampling engine
        for each, and executes the resampling process where applicable.
        Root timeframes (i.e., pass-through sources) are skipped.

        Any error encountered during initialization or execution results in
        a hard failure, allowing the caller or supervising worker to handle
        recovery or termination logic.

        Raises:
            DataNotFoundError: If required input data or dependencies are missing.
            IndexCorruptionError: If an index inconsistency or corruption is detected.
            ProcessingError: If resampling or data validation fails.
            Exception: Propagates any unexpected exceptions to enforce fail-fast
                behavior.
        """
        try:
            for ident in self.config.timeframes:
                # Initialize for this timeframe
                engine = ResampleEngine(self.symbol, ident, self.config, self.data_path)

                # If its a root timeframe, continue
                if engine.is_root:
                    continue

                # Execute the resampling for this timeframe
                self._execute_engine(engine)

        except (DataNotFoundError, IndexCorruptionError, ProcessingError, Exception) as e:
            # Hard fail
            raise
                
                

    def _execute_engine(self, engine: ResampleEngine) -> None:
        """Execute incremental resampling for a single timeframe engine.

        This method drives the full read–process–write loop for a single
        `ResampleEngine`. It supports crash-safe, incremental processing by
        resuming from persisted input and output offsets stored in the index.
        Output writes are performed transactionally to ensure partial results
        are rolled back on failure.

        The last resampled bar of each batch is intentionally held open and
        rewritten on the next iteration to preserve continuity across batch
        boundaries.

        Args:
            engine (ResampleEngine): Initialized resampling engine responsible
                for reading input data, performing resampling logic, and writing
                output and index updates.

        Raises:
            TransactionError: If any operating system–level I/O error occurs
                during reading, writing, or index updates.
        """
        try:
            # Read last known input/output positions from the index
            dt, input_pos, output_pos = engine.index.read()

            # Ensure reader and writer resources are properly managed
            with engine.reader, engine.writer:
                # Resume reading from the last processed input position
                if input_pos > 0:
                    engine.reader.seek(input_pos)

                # Initialize output position if this is the first write
                if output_pos == 0:
                    output_pos = engine.writer.tell()

                # Main incremental processing loop
                while True:
                    # Read the next batch of input data
                    df = engine.reader.read_batch(self.config.batch_size)
                    try:
                        # Resample the batch and compute the next resume offset
                        resampled, next_in_pos = engine.process_resample(df)

                        # Roll back any partial output from a previous failed iteration
                        engine.writer.truncate(output_pos)

                        # Write all but the last bar (held back for continuity)
                        engine.writer.write_batch(resampled.iloc[:-1], output_pos)
                        engine.writer.flush()

                        # Update output position after successful write
                        output_pos = engine.writer.tell()

                        # Persist new input/output positions atomically
                        engine.index.write(next_in_pos, output_pos, dt)

                        # Write the final bar (kept open for next iteration)
                        engine.writer.write_batch(resampled.tail(1))

                    finally:
                        # Explicit finally block reserved for future cleanup hooks
                        pass

                    # Stop once end-of-file is reached
                    if engine.reader.eof():
                        break

                    # Seek to the next input position for incremental processing
                    engine.reader.seek(next_in_pos)

        except OSError as e:
            # Treat any OS-level failure as a transactional I/O error
            raise TransactionError(
                f"I/O failure for {self.symbol} at {engine.ident}: {e}"
            ) from e


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
    try:
        symbol, config = args
        # Initialize the worker
        worker = ResampleWorker(symbol, config)

        # Execute the worker
        worker.run()

    except Exception as e:
        # Raise
        raise ForkProcessError(f"Error on resample fork for {symbol}") from e

    return True



if __name__ == "__main__":
    from etl.config.app_config import *

    import cProfile
    import pstats
    profiler = cProfile.Profile()
    profiler.enable()

    app_config = load_app_config('config.user.yaml')

    fork_resample(["EUR-USD", app_config])

    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(20)
