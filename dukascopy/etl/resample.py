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

from etl.config.app_config import AppConfig, ResampleSymbol, resample_get_symbol_config, ResampleTimeframeProcessingStep
from etl.processors.resample_pre_process import resample_pre_process_origin
from etl.processors.resample_post_process import resample_post_process_merge, resample_post_process_shift
from etl.exceptions import *
import traceback

"""
We are going to make big changes in these classes. IO will get abstracted

- ResampleIOIndexReaderWriter
  Default positioning commit file handling

- EtlIO (abc.ABC) **
- ResampleIOReader (abc.ABC) **
- ResampleIOWriter (abc.ABC) **
- ResampleIOReaderText (Regular handling)
- ResampleIOWriterText (Regular handling)
- ResampleIOReaderBinary (MemoryMapped)
- ResampleIOWriterBinary (MemoryMapped)

- ResampleIOFactory
  To return wither a Text/Binary reader/writer
  get_reader(config), get_writer(config)

Reason:

Profiling indicates that 70-80% of execution time is consumed by CSV 
serialization overhead (read_csv/to_csv). Implementing a fixed-length 
binary mode eliminates this bottleneck via a zero-copy architecture. 
By memory-mapping the file and utilizing np.frombuffer, we create a 
direct memory view that bypasses traditional parsing. Furthermore, 
vectorized offset calculations allow for high-performance, crash-safe indexing. 
This approach is significantly more efficient, shifting the workload from 
CPU-intensive string processing to near-native memory speeds.

Goal: support binary reading writing with fallback for CSV
      binary mode will completely eliminate string parsing

Note: have a look at Protocol, runtime_checkable (Duck Typing) **
      it's a new way for "abstraction". might save some time.

Expected gains:

At the moment, resampling takes about 90 seconds for 42 symbols. 70 percent of that
time is for read_csv and to_csv. The above will eliminate that full 70 percent almost
completely. So, we drop from 90 seconds to about 30 seconds. Half a minute for
resampling 42 symbols, 10 timeframes, average 15-20 years of 1m data per symbol.
Session-handling logic inclusive.

Example:

from typing import Protocol, runtime_checkable

@runtime_checkable
class DataWriter(Protocol):
    def write_at(self, pos: int, data: bytes) -> int:
        ...

class MmapWriter:
    # No explicit inheritance from DataWriter needed!
    def write_at(self, pos: int, data: bytes) -> int:
        return pos + len(data)

def save_data(writer: DataWriter):
    writer.write_at(0, b"OHLCV_DATA")
"""


class ResampleEngine:

    def __init__(
        self,
        symbol: str,
        ident: str,
        config: ResampleSymbol,
        data_path: Path,
    ):
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
        # TODO: changes needed, currently pinned to .csv

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
        if step.action == "merge":
            df = resample_post_process_merge(df, self.ident, step, self.config)
        elif step.action == "shift":
            df = resample_post_process_shift(df, self.ident, step, self.config)
        else:
            print(f"Warning: unknown post-process step {step.action}")

        return df

    def read_index(self) -> Tuple[int, int]:
        # TODO: changes needed, asbtract this function away
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
        # TODO: changes needed, asbtract this function away
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

    def prepare_batch(self, f_input: IO, header: str) -> Tuple[pd.DataFrame, bool]:
        # TODO: changes needed. 
        #       reader must be passed in, header can be eliminated, becomes fixed
        #       reader has read_batch(size) function, returns dataframe with byte positions
        #       in case of binary reader with fixed length records, offset in df
        #       can be a vectorized multiplication start+(id*records_size)
        #       we can make it "zero-copy", use a mmap view and np.frombuffer
        #       this will become very very very fast. no more string/parsing overhead
        sio = StringIO()
        try:
            sio.write(f"{header.strip()},offset\n")
            eof = False
            offset_before = f_input.tell()
            for _ in range(self.config.batch_size):
                line_bytes = f_input.readline()
                if not line_bytes:
                    eof = True
                    break

                line = line_bytes.decode('utf-8').strip()
                sio.write(f"{line.strip()},{offset_before}\n")
                offset_before += len(line_bytes)
            sio.seek(0)
            df = pd.read_csv(
                sio,
                parse_dates=["time"],
                index_col="time",
                date_format="%Y-%m-%d %H:%M:%S",
                low_memory=False,
                sep=',',
            )
            sio.close()
            return df, eof
        except (SessionResolutionError) as e:
            raise BatchError(f"Batch preparation failed for {self.symbol}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected system failure during batching: {e}") from e

    def process_resample(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        # TODO: changes needed
        try:
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                raise ProcessingError(f"Timestamp parsing failed for {self.symbol}: Index is not datetime.")

            if df.empty:
                raise ValueError("Empty batch read from StringIO")

            resampled_list = []

            session = next(iter(self.config.sessions.values()))
            tf_cfg = session.timeframes[self.ident]

            df = self._apply_pre_processing(df, ResampleTimeframeProcessingStep(action="origin"))

            for name, session in self.config.sessions.items():
                tf_pre = session.timeframes.get(self.ident).pre
                if tf_pre:
                    for name, tf_step in tf_pre.items():
                        df = self._apply_pre_processing(df, tf_step)

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

                res = res[res["volume"].gt(0) & res["volume"].notna()]

                if not res.empty:
                    resampled_list.append(res)

            if not resampled_list:
                raise EmptyBatchError(f"Resampling resulted in 0 bars for {self.symbol}.")

            full_resampled = pd.concat(resampled_list).sort_index()

            if "offset" not in full_resampled.columns:
                raise ResampleLogicError(f"Critical: 'offset' column lost during resampling for {self.symbol}.")

            for name, session in self.config.sessions.items():
                tf_post = session.timeframes.get(self.ident).post
                if tf_post:
                    for name, tf_step in tf_post.items():
                        full_resampled = self._apply_post_processing(full_resampled, tf_step)

            # TODO: this will only be necessary for the CSV writer, move it to the CSV writer
            full_resampled.index = full_resampled.index.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            try:
                next_input_pos = int(full_resampled.iloc[-1]["offset"])
            except (IndexError, ValueError, KeyError) as e:
                raise ResampleLogicError(f"Post-processing left no bars for {self.symbol}") from e

            full_resampled = (
                full_resampled.drop(columns=["offset"])
                .round(self.config.round_decimals)
            )

            if full_resampled.isnull().values.any():
                raise ProcessingError(f"Data Error: Result contains NaNs for {self.symbol}")

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

        # Set properties
        self.symbol = symbol
        self.app_config = app_config

        # Load symbol-specific resampling configuration
        self.config = resample_get_symbol_config(symbol, app_config)

        # Root directory for resampled data
        self.data_path = Path(app_config.resample.paths.data)

    def run(self) -> None:

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
        # TODO: changes needed
        try:
            # TODO: setup index, writer, reader (or do in constructor)

            # TODO: index.READ()
            input_pos, output_pos = engine.read_index()

            with open(engine.input_path, "rb") as f_in, open(engine.output_path, "r+") as f_out:
                
                # TODO: reader.READ-HEADER function
                header_bytes = f_in.readline()
                header = header_bytes.decode('utf-8')
                if input_pos > 0: f_in.seek(input_pos)

                # TODO: writer.WRITE-HEADER function
                if output_pos == 0:
                    f_out.write(header)
                    output_pos = f_out.tell()

                while True:
                    # TODO: pass in reader, eliminate eof
                    df, eof = engine.prepare_batch(f_in, header)
                    try:
                        # This remains unchanged
                        resampled, next_in_pos = engine.process_resample(df)

                        # TODO: writer.WRITE_AT(output_pos, df, [truncate=true, fsync=self.config.fsync])
                        f_out.seek(output_pos)
                        f_out.truncate(output_pos)
                        f_out.write(resampled.iloc[:-1].to_csv(index=True, header=False))
                        f_out.flush()
                        if self.config.fsync: os.fsync(f_out.fileno())
                        
                        # TODO: output_pos = writer.TELL()
                        output_pos = f_out.tell()

                        # TODO: index.WRITE(next_in_pos, output_pos)
                        engine.write_index(next_in_pos, output_pos)
                        
                        # TODO: writer.WRITE(df)
                        f_out.write(resampled.tail(1).to_csv(index=True, header=False))

                    finally:
                        pass

                    # TODO: reader.EOF()
                    if eof:
                        break
                    
                    # TODO: reader.SEEK
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
