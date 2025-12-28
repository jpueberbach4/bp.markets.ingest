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

 Description:
     Incremental, crash-safe OHLCV resampling engine with session awareness.

     This module implements an object-oriented resampling pipeline designed
     to transform high-frequency OHLCV CSV data into derived timeframes
     (e.g. 1m → 5m → 1h) in a resumable, fault-tolerant manner.

     Core design goals:
         - Incremental batch-based processing for large datasets
         - Session-aware resampling with strict boundary isolation
         - Crash-safe progress tracking via persisted byte offsets
         - Idempotent recovery after partial failures
         - Explicit dependency ordering between timeframes

     Main components:

     - ResampleEngine
         Handles resampling for a single symbol and timeframe.
         Responsibilities include:
             * Resolving and validating input/output/index paths
             * Reading source data incrementally in fixed-size batches
             * Enriching rows with session-aware origin metadata
             * Performing pandas-based OHLCV resampling
             * Applying optional post-processing rules
             * Persisting progress using atomic index updates

     - ResampleWorker
         Orchestrates resampling across all configured timeframes for a symbol.
         Responsibilities include:
             * Enforcing cascading timeframe dependencies
             * Skipping root (pass-through) timeframes
             * Executing derived timeframe engines sequentially
             * Failing fast on any unrecoverable error

     Execution model:
         - Input CSVs are read incrementally using byte offsets.
         - Output CSVs are written using a two-phase commit strategy:
             * Fully completed bars are fsync-committed and indexed.
             * A trailing partial bar is written optimistically and may
               be recomputed on restart.
         - Index files store the last confirmed input/output positions and
           guarantee safe resume after crashes or restarts.

     Failure semantics:
         - Any data corruption, logic error, or I/O failure causes
           immediate termination.
         - No downstream timeframes are processed after a failure.
         - Partial output is safely rolled back and recomputed on restart.

     Intended usage:
         - Offline or scheduled batch resampling
         - Deterministic, auditable market data pipelines
         - Large CSV datasets that cannot be processed in-memory

===============================================================================
"""
import os
import pandas as pd
import numpy as np
from pathlib import Path
from io import StringIO
from typing import Tuple, IO, Optional

from config.app_config import AppConfig, ResampleSymbol, resample_get_symbol_config, ResampleTimeframeProcessingStep
from processors.resample_pre_process import preprocess_origin
from helper import ResampleTracker
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
        if step.action == "originxx":
            # This is a very complicated routine being called
            df = preprocess_origin(self.config.timezone, df, self.ident, self.config)

        return df

    def _apply_post_processing(
        self,
        df: pd.DataFrame,
        step: ResampleTimeframeProcessingStep
    ) -> pd.DataFrame:
        """Apply configured post-processing operations to a resampled DataFrame.

        This method currently supports a single post-processing action: ``merge``.
        The merge operation identifies rows whose index ends with one of the
        suffixes defined in ``step.ends_with`` and merges each of those rows into
        an anchor row determined by ``step.offset``.

        For each matching row:
            - The anchor row is selected using ``anchor_pos = pos + step.offset``.
            - OHLCV fields are merged as follows:
                * ``high``   → max(anchor.high, selected.high)
                * ``low``    → min(anchor.low, selected.low)
                * ``close``  → selected.close
                * ``volume`` → anchor.volume + selected.volume
            - The selected row is removed from the DataFrame after merging.

        Processing is performed in positional index order and operates directly
        on the provided DataFrame.

        Important constraints:
            - The DataFrame index **must** be string-based and support
            ``str.endswith``.
            - ``step.offset`` must resolve to a valid row position; otherwise
            post-processing fails hard.
            - Date-range filtering (``from_date`` / ``to_date``) is not implemented.

        Args:
            df (pd.DataFrame):
                Resampled OHLCV data. The index is expected to contain string-form
                timestamps representing resampled time buckets.
            step (ResampleTimeframeProcessingStep):
                Post-processing configuration defining the action type, suffixes
                to match, and positional offset used to determine merge targets.

        Returns:
            pd.DataFrame:
                A DataFrame with matched rows merged into their anchors and
                removed from the result.

        Raises:
            ValueError:
                If the configured post-processing action is not supported.
            PostProcessingError:
                If the merge offset resolves to an invalid anchor position.
        """

        if step.action != "merge":
            raise ValueError(f"Unsupported post-processing action {step.action}")

        offset = step.offset
        for ends_with in step.ends_with:
            positions = np.where(df.index.str.endswith(ends_with))[0]

            for pos in positions:
                # Ensure there is a row before the selects to merge into
                if pos > 0:
                    anchor_pos = pos + offset
                    # Make sure the anchor_pos is actually existing
                    if 0 <= anchor_pos < len(df):

                        # Get index of select and the anchor
                        select_idx = df.index[pos]
                        anchor_idx = df.index[anchor_pos]

                        # Perform the logic, determine high, low, close and sum volume
                        df.at[anchor_idx, 'high'] = max(
                            df.at[anchor_idx, 'high'],
                            df.at[select_idx, 'high'],
                        )
                        df.at[anchor_idx, 'low'] = min(
                            df.at[anchor_idx, 'low'],
                            df.at[select_idx, 'low'],
                        )
                        df.at[anchor_idx, 'close'] = df.at[select_idx, 'close']
                        df.at[anchor_idx, 'volume'] += df.at[select_idx, 'volume']
                    else:
                        # Error in offset definition, fail!
                        raise PostProcessingError(f"Post-processing error for {self.symbol} at timeframe {self.ident}")


            # Drop all selected source columns
            df = df[~df.index.str.endswith(ends_with)]

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
        """Read and enrich a batch of input CSV rows for resampling.

        Reads up to ``config.batch_size`` rows from the input CSV file and writes
        them into an in-memory CSV buffer, extending each row with resampling
        metadata required for downstream processing.

        Each output row is augmented with:
            - ``origin``: The session-aware resampling origin timestamp.
            - ``offset``: The byte offset in the input file immediately before
            the row was read.

        Origin resolution behavior:
            - If a single (default) session is configured, a precomputed origin
            is reused for all rows.
            - If multiple sessions are configured, the active session is resolved
            per row and the origin is recomputed only when the session or
            calendar day changes.

        The returned buffer includes the original CSV header with the additional
        metadata columns appended.

        Args:
            f_input (IO):
                Open input CSV file handle positioned at the next unread row.
            header (str):
                Original CSV header line, including the trailing newline.

        Returns:
            Tuple[StringIO, bool]:
                A tuple ``(buffer, eof)`` where:
                - ``buffer`` is a ``StringIO`` object containing the enriched CSV
                batch, positioned at the beginning for reading.
                - ``eof`` is ``True`` if end-of-file was reached during batch
                preparation, otherwise ``False``.

        Raises:
            SessionResolutionError:
                If a row cannot be mapped to a valid trading session or origin.
            BatchError:
                If batch preparation fails due to session resolution errors.
            RuntimeError:
                If an unexpected system-level error occurs during batching.
        """
        # Initialize in-memory buffer for the output batch
        sio = StringIO()
        try:

            # Write CSV header with appended metadata columns
            sio.write(f"{header.strip()},origin,offset\n")

            # Track end-of-file state and last processed session/day key
            eof = False
            last_key = None

            # Check whether the tracker is running in single-session mode
            is_default = self.tracker.is_default_session()

            # Precompute origin for the single-session (default) case
            primary_session = next(iter(self.config.sessions.values()))
            origin = default_origin = primary_session.timeframes[self.ident].origin

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

                line = line_bytes.decode('utf-8').strip()

                # Resolve origin dynamically when multiple sessions are configured
                if False:
                    # Disabled the line-by-line origin sets
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
                            raise SessionResolutionError(
                                f"Session mapping failed for {self.symbol} at line: {line.strip()}"
                            ) from e
                    else:
                        # Use precomputed origin for single-session mode
                        origin = default_origin

                # Write the enriched CSV row to the output buffer
                sio.write(f"{line.strip()},{origin},{offset_before}\n")

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
        """Resample a prepared CSV batch into the configured target timeframe.

        The input batch is parsed into a DataFrame indexed by timestamp and grouped
        by ``origin``. Each origin group is resampled independently to preserve
        session boundaries and avoid cross-session bar contamination.

        For each origin group, OHLCV bars are produced using the timeframe rule and
        aggregation settings defined in the primary session configuration. Empty or
        invalid bars (e.g. zero or NaN volume) are discarded.

        Post-processing steps defined on the timeframe (if any) are applied after
        all origins are combined into a single, time-sorted DataFrame.

        The resume offset for the next batch is derived from the ``offset`` value of
        the final completed resampled bar.

        Args:
            sio (StringIO):
                In-memory CSV buffer produced by ``prepare_batch``, including the
                appended ``origin`` and ``offset`` metadata columns.

        Returns:
            Tuple[pd.DataFrame, int]:
                A tuple ``(df, next_input_pos)`` where:
                - ``df`` is the resampled OHLCV DataFrame indexed by formatted
                timestamp strings.
                - ``next_input_pos`` is the byte offset in the input CSV from which
                the next batch should resume.

        Raises:
            ValueError:
                If the prepared batch contains no rows.
            EmptyBatchError:
                If resampling produces zero valid bars across all origins.
            ProcessingError:
                If timestamp parsing fails, NaNs are produced, or an unexpected
                processing error occurs.
            ResampleLogicError:
                If required metadata (e.g. ``offset``) is lost or post-processing
                invalidates all bars.
        """
        try:
            # Load the prepared CSV batch into a DataFrame indexed by timestamp
            df = pd.read_csv(
                sio,
                parse_dates=["time"],
                index_col="time",
                date_format="%Y-%m-%d %H:%M:%S",
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

            # We inject the new origin marker here (it has now become a vectorized pre-processing step)
            pre_processing_steps = [ResampleTimeframeProcessingStep(action="origin")] + \
                                    (list(tf_cfg.pre.values()) if tf_cfg.pre else [])

            # Apply pre-processing
            for tf_step in pre_processing_steps:
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

            # Apply post-processing (currently ugly, improve in future)
            if tf_cfg.post:
                for tf_step in tf_cfg.post.values():
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


def fork_resample_profile(args):
    import cProfile
    import pstats
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        symbol, config = args
        # Initialize the worker
        worker = ResampleWorker(symbol, config)

        # Execute the worker
        worker.run()
    finally:
        profiler.disable()
        
        # Save profiling stats
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 bottlenecks


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
        return fork_resample_profile(args)
        symbol, config = args
        # Initialize the worker
        worker = ResampleWorker(symbol, config)

        # Execute the worker
        worker.run()

    except Exception as e:
        # Raise
        raise ForkProcessError(f"Error on resample fork for {symbol}") from e

    return True

