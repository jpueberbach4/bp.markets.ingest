#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resample.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Updated:     2025-12-23
              Strengthening of code
              - Optional fsync
              - Custom exceptions for better traceability
              2025-12-28
              Vectorization of session logic
              - Normalized session logic to a pre-process step
              - Normalized post- and pre-processing

 Description: Object-oriented, crash-safe OHLCV resampling engine with session and DST awareness.

              This module implements an incremental resampling pipeline for
              high-frequency OHLCV data, transforming it into derived
              timeframes (e.g., 1m → 5m → 1h) while ensuring:
                - Session-aware bar generation
                - DST-aware origin handling
                - Incremental, resumable batch processing
                - Idempotent recovery after partial failures
                - Explicit dependency ordering between timeframes

              Key classes:
                - ResampleEngine: Handles resampling for a single symbol/timeframe.
                - ResampleWorker: Orchestrates resampling across all configured
                  timeframes for a symbol.
              
              Features:
                - Vectorized pre-processing for session origins
                - Post-processing for merging intermediate bars
                - Crash-safe index persistence for input/output offsets
                - Optional fsync to guarantee data durability

 Usage:
     - Imported and executed by a resampling scheduler or forked per symbol.
     - Can also be invoked in multiprocessing contexts.

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

from config.app_config import AppConfig, ResampleSymbol, resample_get_symbol_config, ResampleTimeframeProcessingStep
from processors.resample_pre_process import resample_pre_process_origin
from processors.resample_post_process import resample_post_process_merge
from exceptions import *
import traceback

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
        # Set properties
        self.symbol = symbol
        self.ident = ident
        self.config = config

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
        """Resolve and validate filesystem paths for the current timeframe.

        Determines whether the configured timeframe is a root (pass-through)
        timeframe or a derived (resampled) timeframe and resolves all required
        input, output, and index paths accordingly.

        Root timeframes:
            - Have no resampling rule defined.
            - Use an external CSV as both input and output.
            - Do not use an index file.
            - Are marked as ``is_root = True``.

        Derived timeframes:
            - Are resampled from another timeframe (root or derived).
            - Resolve their input CSV either from:
                * another derived timeframe under ``data_path``, or
                * an external CSV if the source timeframe is root.
            - Define an output CSV under ``data_path/<ident>/<symbol>.csv``.
            - Define an index file under
            ``data_path/<ident>/index/<symbol>.idx`` for resumable processing.
            - Ensure the output directory and CSV file exist.

        This method performs validation of all upstream dependencies and fails
        fast if required source data is missing or misconfigured.

        Raises:
            DataNotFoundError:
                If a required root CSV or upstream dependency does not exist.
            ValueError:
                If the timeframe references an unknown or invalid source timeframe.
        """

        timeframe = self.config.timeframes.get(self.ident)

        # Root timeframe: pass-through source (e.g. 1m CSV)
        if not timeframe.rule:
            root_source = Path(timeframe.source) / f"{self.symbol}.csv"

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
            input_path = self.data_path / timeframe.source / f"{self.symbol}.csv"
        else:
            # Source is an external CSV
            input_path = Path(source_tf.source) / f"{self.symbol}.csv"

        # Output CSV and index file locations
        output_path = self.data_path / self.ident / f"{self.symbol}.csv"
        index_path = self.data_path / self.ident / "index" / f"{self.symbol}.idx"

        # Validate that upstream data exists
        if not input_path.exists():
            raise DataNotFoundError(f"Dependency missing: {self.symbol} needs {timeframe.source} first.")

        # Ensure output directory and file exist
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Create empty file
            output_path.touch()

        # Update properties
        self.input_path = input_path
        self.output_path = output_path
        self.index_path = index_path
        self.is_root = False

    def _apply_pre_processing(self, df: pd.DataFrame, step: ResampleTimeframeProcessingStep) -> pd.DataFrame:
        """Apply pre-processing actions to a DataFrame before resampling.

        This method dispatches pre-processing logic based on the action defined
        in the resampling step configuration. Pre-processing is typically used
        to enrich the input data with additional metadata required for correct
        resampling behavior, such as computing session origins in a
        timezone- and DST-aware manner.

        Args:
            df (pd.DataFrame): Input OHLCV data to be pre-processed.
            step (ResampleTimeframeProcessingStep): Processing step definition
                specifying the pre-processing action and its parameters.

        Returns:
            pd.DataFrame: The pre-processed DataFrame.

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
        """Apply post-processing actions to a resampled DataFrame.

        This method dispatches post-processing logic based on the action defined
        in the resampling step configuration. Currently, it supports merging
        intermediate rows into anchor rows via the ``merge`` action.

        Args:
            df (pd.DataFrame): Resampled OHLCV data to be post-processed.
            step (ResampleTimeframeProcessingStep): Processing step definition
                specifying the post-processing action and its parameters.

        Returns:
            pd.DataFrame: The post-processed DataFrame.

        """
        if step.action == "merge":
            df = resample_post_process_merge(df, self.ident, step, self.config)
        else:
            print(f"Warning: unknown post-process step {step.action}")

        return df


    def read_index(self) -> Tuple[int, int]:
        """Read persisted input and output byte offsets from the index file.

        The index file is expected to contain two newline-separated integers:
        the input file byte offset on the first line and the output file byte
        offset on the second line.

        If the index file does not exist, it is created and initialized with
        zero offsets (``0, 0``).

        This method performs minimal validation and fails fast if the index
        contents are unreadable or incomplete.

        Returns:
            Tuple[int, int]:
                A tuple ``(input_pos, output_pos)`` where:
                - ``input_pos`` is the byte offset to resume reading the input CSV.
                - ``output_pos`` is the byte offset to resume writing the output CSV.

        Raises:
            IndexCorruptionError:
                If the index file exists but cannot be parsed as two integers
                (e.g., partial writes, truncation, or invalid content).
            IndexWriteError:
                If initialization of a missing index file fails.
        """
        try:
            # Initialize index if missing
            if not self.index_path or not self.index_path.exists():
                self.write_index(0, 0)
                return 0, 0

            # Read the first two lines (input_pos, output_pos)
            with open(self.index_path, "r") as f:
                lines = f.readlines()[:2]
        
            # No length check needed, caught by IndexError
            return int(lines[0].strip()), int(lines[1].strip())

        except (ValueError, IndexError) as e:
            
            raise IndexCorruptionError(f"Corrupt index at {self.index_path}. Check for partial writes.") from e


    def write_index(self, input_pos: int, output_pos: int) -> None:
        """Persist input and output byte offsets to the index file atomically.

        Writes the provided input and output byte offsets to the index file as
        two newline-separated integers. Persistence is performed using a
        write-to-temp-and-replace strategy to ensure crash safety.

        The index directory is created automatically if it does not already exist.

        Args:
            input_pos (int):
                Byte offset indicating where to resume reading the input CSV.
            output_pos (int):
                Byte offset indicating where to resume writing the output CSV.

        Raises:
            IndexValidationError:
                If either offset is negative.
            IndexWriteError:
                If the index directory cannot be created or the index file
                cannot be written or replaced due to an OS-level failure
                (e.g. permission denied, disk full).
        """
        if input_pos < 0 or output_pos < 0:
            raise IndexValidationError(
                f"Invalid offsets for {self.symbol}: IN={input_pos}, OUT={output_pos}"
            )
        try:
            # Ensure index directory exists
            self.index_path.parent.mkdir(parents=True, exist_ok=True)

            # Write offsets to a temporary file
            temp_path = self.index_path.with_suffix(".tmp")

            with open(temp_path, "w") as f:
                # Write positions
                f.write(f"{input_pos}\n{output_pos}")
                # Flush to OS
                f.flush()
                # Force persist to disk
                if self.config.fsync:
                    os.fsync(f.fileno())

            # Atomic replace
            os.replace(temp_path, self.index_path)
        
        except OSError as e:
            # Disk full, Permission denied, etc.
            raise IndexWriteError(
                f"Failed to persist index for {self.symbol}: {e}"
            ) from e

    def prepare_batch(self, f_input: IO, header: str) -> Tuple[StringIO, bool]:
        """Prepare and enrich a batch of CSV rows for resampling.

        Reads up to `config.batch_size` rows from the input CSV file and writes
        them into an in-memory CSV buffer. Each row is augmented with resampling
        metadata, including the byte offset in the input file, which is required
        for incremental and resumable processing.

        The returned buffer includes:
            - The original CSV header with an additional `offset` column.
            - Each row enriched with the `offset` indicating the input file
            position prior to reading the row.

        This method efficiently tracks the file read position to support large
        CSVs without loading them entirely into memory.

        Args:
            f_input (IO):
                Open CSV file handle positioned at the next unread row.
            header (str):
                CSV header line including the newline character.

        Returns:
            Tuple[StringIO, bool]:
                A tuple containing:
                - `buffer` (StringIO): In-memory CSV buffer containing the batch
                with appended metadata, ready for processing.
                - `eof` (bool): True if the end of the input file was reached
                during this batch; False otherwise.

        Raises:
            SessionResolutionError:
                If a row cannot be mapped to a valid trading session or origin.
            BatchError:
                If batch preparation fails due to session resolution or related errors.
            RuntimeError:
                If an unexpected system-level error occurs during batching, such
                as I/O or decoding failures.
        """
        # Initialize in-memory buffer for the output batch
        sio = StringIO()
        try:

            # Write CSV header with appended metadata columns
            sio.write(f"{header.strip()},offset\n")

            # Track end-of-file state and last processed session/day key
            eof = False
            last_key = None

            # Get the current position (we are changing the tell since it massively impacts performance)
            offset_before = f_input.tell()

            # Read up to batch_size rows from the input file
            for _ in range(self.config.batch_size):
                # Capture byte offset before reading the row
               
                line_bytes = f_input.readline()

                # Stop processing if end-of-file is reached
                if not line_bytes:
                    eof = True
                    break

                # Strip any newlines
                line = line_bytes.decode('utf-8').strip()

                # Write the enriched CSV row to the output buffer
                sio.write(f"{line.strip()},{offset_before}\n")

                # Update offset_before
                offset_before += len(line_bytes)

            # Reset buffer cursor for downstream consumers
            sio.seek(0)

            # Return the StrinIO and a boolean indicating eof yes/no
            return sio, eof

        except (SessionResolutionError) as e:
            raise BatchError(f"Batch preparation failed for {self.symbol}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected system failure during batching: {e}") from e

    def process_resample(self, sio: StringIO) -> Tuple[pd.DataFrame, int]:
        """Resample a batch of CSV rows into the configured target timeframe.

        This method parses an in-memory CSV batch produced by `prepare_batch`,
        applies pre-processing steps (including session origin assignment),
        and resamples the data into OHLCV bars according to the configured
        timeframe rule. Each unique `origin` is processed independently to
        preserve session boundaries and avoid cross-session contamination.

        Resampling:
            - Aggregates 'open', 'high', 'low', 'close', 'volume', and retains
            'offset' for incremental batch tracking.
            - Discards bars with zero or NaN volume.
            - Applies optional post-processing steps defined in the timeframe
            configuration after combining all origin groups.

        The next input position is derived from the 'offset' of the last
        completed bar, allowing resumable incremental processing.

        Args:
            sio (StringIO): In-memory CSV buffer including columns:
                - time: timestamp
                - OHLCV columns
                - origin: session-aware origin timestamp
                - offset: byte position in the input CSV before reading the row

        Returns:
            Tuple[pd.DataFrame, int]:
                - df: Resampled OHLCV DataFrame indexed by timestamp strings,
                rounded according to configuration.
                - next_input_pos: Byte offset in the input CSV to resume
                processing the next batch.

        Raises:
            ValueError: If the CSV batch contains no rows.
            EmptyBatchError: If resampling produces zero valid bars across all
                origin groups.
            ProcessingError: If timestamp parsing fails, NaNs are introduced,
                or an unexpected error occurs during processing.
            ResampleLogicError: If required metadata (e.g., 'offset') is lost
                or post-processing invalidates all bars.
        """
        try:
            # Load the prepared CSV batch into a DataFrame indexed by timestamp
            df = pd.read_csv(
                sio,
                parse_dates=["time"],
                index_col="time",
                date_format="%Y-%m-%d %H:%M:%S",
                low_memory=False,
                sep=',',
            )

            # If anything in the index is not a valid datetime
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                raise ProcessingError(f"Timestamp parsing failed for {self.symbol}: Index is not datetime.")

            # Guard against empty batches
            if df.empty:
                raise ValueError("Empty batch read from StringIO")

            # Accumulate per-origin resampled DataFrames
            resampled_list = []

            # Retrieve timeframe configuration from the primary session
            session = next(iter(self.config.sessions.values()))
            tf_cfg = session.timeframes[self.ident]

            # Origin pre-processing always needs to occur, once per df
            df = self._apply_pre_processing(df, ResampleTimeframeProcessingStep(action="origin"))

            # Apply pre-processing, limited by session boundaries (weekdays, date-range)
            for name, session in self.config.sessions.items():
                tf_pre = session.timeframes.get(self.ident).pre
                if tf_pre:
                    for name, tf_step in tf_pre.items():
                        df = self._apply_pre_processing(df, tf_step)

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

                # If we have an empty dataframe, we dont append it
                if not res.empty:
                    resampled_list.append(res)

            # If no dataframes collected, error out
            if not resampled_list:
                raise EmptyBatchError(f"Resampling resulted in 0 bars for {self.symbol}.")

            # Combine all resampled origins into a single, time-sorted DataFrame
            full_resampled = pd.concat(resampled_list).sort_index()

            # If we lost the offset column (somehow)
            if "offset" not in full_resampled.columns:
                raise ResampleLogicError(f"Critical: 'offset' column lost during resampling for {self.symbol}.")

            # Normalize index formatting for downstream consumers
            full_resampled.index = full_resampled.index.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # Apply post-processing, limited by its sessions boundaries (weekdays, date-range)
            for name, session in self.config.sessions.items():
                tf_post = session.timeframes.get(self.ident).post
                if tf_post:
                    for name, tf_step in tf_post.items():
                        full_resampled = self._apply_post_processing(full_resampled, tf_step)

            # Determine the resume position from the last completed bar
            try:
                next_input_pos = int(full_resampled.iloc[-1]["offset"])
            except (IndexError, ValueError, KeyError) as e:
                # If post-processing cleared the whole dataframe, we CRASH here.
                raise ResampleLogicError(f"Post-processing left no bars for {self.symbol}") from e

            # Remove internal metadata and apply final rounding
            full_resampled = (
                full_resampled.drop(columns=["offset"])
                .round(self.config.round_decimals)
            )

            # Make sure we dont have any NaN values
            if full_resampled.isnull().values.any():
                raise ProcessingError(f"Data Error: Result contains NaNs for {self.symbol}")

            # Return the dataframe and the input_position to start next batch at
            return full_resampled, next_input_pos
        except (EmptyBatchError, ResampleLogicError, ProcessingError):
            # Re-raise known errors
            raise
        except Exception as e:
            # Wrap everything in ProcessingError to trigger the Worker's crash logic
            raise ProcessingError(f"Fail-Fast triggered: {e}") from e

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
        # Set properties
        self.symbol = symbol
        self.app_config = app_config

        # Load symbol-specific resampling configuration
        self.config = resample_get_symbol_config(symbol, app_config)

        # Root directory for resampled data
        self.data_path = Path(app_config.resample.paths.data)

    def run(self) -> None:
        """Execute resampling for all configured timeframes in dependency order.

        Iterates sequentially over all timeframes defined in the configuration and
        executes resampling for each derived timeframe using a dedicated
        ``ResampleEngine`` instance.

        Root (source) timeframes are detected and skipped, as they do not require
        resampling. Derived timeframes are processed in configuration order, which
        implicitly enforces cascading dependencies (e.g. lower timeframes must
        succeed before higher timeframes can be produced).

        If a failure occurs while processing any timeframe, execution stops
        immediately and no subsequent (higher) timeframes are attempted.

        Raises:
            DataNotFoundError:
                If a required input dataset for any timeframe is missing.
            IndexCorruptionError:
                If a persisted resampling index is unreadable or invalid.
            ProcessingError:
                If resampling fails due to parsing, aggregation, or logic errors.
            Exception:
                Any unexpected exception, which is logged and re-raised after
                printing a full traceback.
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
        """Execute the incremental resampling loop for a single derived timeframe.

        This method performs crash-safe, batch-oriented resampling using persisted
        input/output offsets. Progress is restored from index files and committed
        incrementally to ensure idempotent recovery after failures.

        Execution flow:
            1. Restore last confirmed input and output byte offsets.
            2. Resume reading the input CSV and appending to the output CSV.
            3. Process input data in fixed-size batches.
            4. Atomically commit fully completed bars and persist progress.
            5. Write a trailing (potentially partial) bar for continuation.

        Atomicity and safety guarantees:
            - Fully completed bars are only committed after a successful batch
            resample and forced disk flush (``fsync``).
            - Progress indices are updated only after confirmed output writes.
            - On restart, partially written trailing bars are discarded and
            recomputed.

        Args:
            engine (ResampleEngine):
                Initialized resampling engine for a derived timeframe.

        Raises:
            TransactionError:
                If any I/O operation fails during batch processing or commit.
            DataNotFoundError:
                If required input data is missing.
            ProcessingError:
                If batch preparation or resampling fails.
        """
        try:
            # Restore last known read/write positions from index files
            input_pos, output_pos = engine.read_index()

            # Open input CSV for reading and output CSV for read/write updates
            with open(engine.input_path, "rb") as f_in, open(engine.output_path, "r+") as f_out:
                # Read and cache the input CSV header
                header_bytes = f_in.readline()
                
                # We are now operating in bytes mode
                header = header_bytes.decode('utf-8')

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
                        
                        # Roll back output file to the last confirmed safe position
                        f_out.seek(output_pos)
                        f_out.truncate(output_pos)

                        # Write all fully completed bars (exclude trailing partial bar)
                        f_out.write(resampled.iloc[:-1].to_csv(index=True, header=False))
                        # Flush to OS
                        f_out.flush()
                        # Force persist to disk
                        if self.config.fsync:
                            os.fsync(f_out.fileno())
                        # Read the position in output file
                        output_pos = f_out.tell()
                        # Persist progress after writing confirmed bars
                        engine.write_index(next_in_pos, output_pos)

                        # Write the trailing bar, which may be updated in the next batch
                        f_out.write(resampled.tail(1).to_csv(index=True, header=False))

                    finally:
                        # Clear memory allocated by StringIO
                        sio.close()

                    # If we reached end of file in resample_batch
                    if eof:
                        break
                    
                    # Always jump to the end of the processed batch
                    f_in.seek(next_in_pos)

        except OSError as e:
            # Any OS Error
            raise TransactionError(f"I/O failure for {self.symbol} at {engine.ident}: {e}") from e

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
