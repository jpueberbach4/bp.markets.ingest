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


from etl.io.protocols import *  # lazy for a moment
from etl.exceptions import *

from etl.io.resample.factory import ResampleIOFactory
import traceback




class ResampleEngine:

    def __init__(
        self,
        symbol: str,
        ident: str,
        config: ResampleSymbol,
        data_path: Path,
    ):

        # Set primary IO mode
        self.fmode = config.fmode

        # Set properties
        self.symbol = symbol
        self.ident = ident
        self.config = config

        # Root directory for resampled CSVs
        self.data_path = data_path

        # Setup IO
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

        # Setup IO
        self.index = ResampleIOFactory.get_index_handler(self.index_path, self.fmode, fsync=self.config.fsync)
        self.reader = ResampleIOFactory.get_reader(self.input_path, self.fmode)
        self.writer =  ResampleIOFactory.get_writer(self.output_path, self.fmode, fsync=self.config.fsync)
        # Done setting up IO, next routine


    def _resolve_paths(self) -> None:
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

    def process_resample(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
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

        try:
            input_pos, output_pos = engine.index.read()

            with engine.reader, engine.writer:
                if input_pos > 0:
                    engine.reader.seek(input_pos)

                if output_pos == 0:
                    output_pos = engine.writer.tell()

                while True:
                    df = engine.reader.read_batch(self.config.batch_size)
                    try:
                        resampled, next_in_pos = engine.process_resample(df)

                        engine.writer.truncate(output_pos)
                        engine.writer.write_batch(resampled.iloc[:-1], output_pos)
                        engine.writer.flush()

                        output_pos = engine.writer.tell()
                        engine.index.write(next_in_pos, output_pos)
                        engine.writer.write_batch(resampled.tail(1))

                    finally:
                        pass

                    if engine.reader.eof():
                        break
                    
                    engine.reader.seek(next_in_pos)

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



if __name__ == "__main__":
    from etl.config.app_config import *

    app_config = load_app_config('config.user.yaml')

    fork_resample(["EUR-USD", app_config])

