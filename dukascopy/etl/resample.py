#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        helper.py
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

 Requirements:
     - Python 3.8+
     - Pandas
     - Tqdm

 License:
     MIT License
===============================================================================
"""
import os
import pandas as pd
from pathlib import Path
from io import StringIO
from typing import Tuple, IO, Optional
from tqdm import tqdm

from config.app_config import AppConfig, ResampleSymbol, resample_get_symbol_config
from helper import ResampleTracker

# Enable verbose logging via environment variable
VERBOSE = os.getenv('VERBOSE', '0').lower() in ('1', 'true', 'yes', 'on')


class ResampleEngine:
    """
    Performs incremental resampling for a single symbol and timeframe.

    The engine:
    - Resolves input/output/index file paths
    - Tracks read/write offsets for resumable processing
    - Reads input data in batches
    - Applies pandas resampling rules
    """

    def __init__(self, symbol: str, ident: str, config: ResampleSymbol, data_path: Path):
        """
        Initialize the resampling engine for a specific symbol and timeframe.

        Args:
            symbol: Trading symbol (e.g. "BTCUSDT")
            ident: Timeframe identifier (e.g. "5m", "1h")
            config: Symbol-specific resampling configuration
            data_path: Base directory for resampled data
        """
        self.symbol = symbol
        self.ident = ident
        self.config = config
        self.tracker = ResampleTracker(config)
        self.data_path = data_path

        # Paths and state resolved dynamically
        self.input_path: Optional[Path] = None
        self.output_path: Optional[Path] = None
        self.index_path: Optional[Path] = None
        self.is_root: bool = False

        # Resolve all filesystem paths immediately
        self._resolve_paths()

    def _resolve_paths(self):
        """
        Resolve input, output, and index paths for the current timeframe.

        Determines whether the timeframe is a root (non-resampled) source
        or derived from another timeframe, validates required files,
        and prepares output directories if needed.
        """
        timeframe = self.config.timeframes.get(self.ident)

        # Root timeframe: no resampling rule, source is external CSV
        if not timeframe.rule:
            root_source = Path(f"{timeframe.source}/{self.symbol}.csv")
            if not root_source.exists():
                raise IOError(f"Root source missing for {self.ident}: {root_source}")

            self.input_path = None
            self.output_path = root_source
            self.index_path = Path()
            self.is_root = True
            return

        # Locate source timeframe configuration
        source_tf = self.config.timeframes.get(timeframe.source)
        if not source_tf:
            raise ValueError(
                f"Timeframe {self.ident} references unknown source: {timeframe.source}"
            )

        # Determine input path based on whether the source itself is resampled
        if source_tf.rule is not None:
            input_path = self.data_path / timeframe.source / f"{self.symbol}.csv"
        else:
            input_path = Path(source_tf.source) / f"{self.symbol}.csv"

        # Define output CSV and index file paths
        output_path = self.data_path / self.ident / f"{self.symbol}.csv"
        index_path = self.data_path / self.ident / "index" / f"{self.symbol}.idx"

        # Validate input existence
        if not input_path.exists():
            if VERBOSE:
                tqdm.write(f"  No base {self.ident} data for {self.symbol} → skipping")
            raise ValueError(f"No base data for {self.symbol} at {self.ident}")

        # Ensure output file exists
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.touch()

        self.input_path = input_path
        self.output_path = output_path
        self.index_path = index_path
        self.is_root = False

    def read_index(self) -> Tuple[int, int]:
        """
        Read the persisted input/output offsets from the index file.

        Returns:
            A tuple of (input_position, output_position)
        """
        if not self.index_path or not self.index_path.exists():
            # Initialize index if missing
            self.write_index(0, 0)
            return 0, 0

        with open(self.index_path, 'r') as f:
            lines = f.readlines()[:2]
            if len(lines) == 2:
                return int(lines[0].strip()), int(lines[1].strip())
            return 0, 0

    def write_index(self, input_pos: int, output_pos: int):
        """
        Atomically write updated input/output offsets to disk.

        Args:
            input_pos: Byte offset in the input file
            output_pos: Byte offset in the output file
        """
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file for atomic replace
        temp_path = self.index_path.with_suffix('.tmp')
        with open(temp_path, "w") as f:
            f.write(f"{input_pos}\n{output_pos}")
            f.flush()

        os.replace(temp_path, self.index_path)

    def prepare_batch(self, f_input: IO, header: str) -> Tuple[StringIO, bool]:
        """
        Read a batch of raw rows and enrich them with origin and offset data.

        Args:
            f_input: Open input file handle
            header: CSV header line

        Returns:
            A tuple of (StringIO buffer containing batch CSV data, eof flag)
        """
        sio = StringIO()
        sio.write(f"{header.strip()},origin,offset\n")

        eof = False
        last_key = None

        # Session/origin resolution helpers
        is_default = self.tracker.is_default_session(self.config)
        primary_session = next(iter(self.config.sessions.values()))
        default_origin = primary_session.timeframes.get(self.ident).origin

        # Read up to batch_size lines
        for _ in range(self.config.batch_size):
            offset_before = f_input.tell()
            line = f_input.readline()

            if not line:
                eof = True
                break

            # Resolve origin dynamically if sessions are non-default
            if not is_default:
                session = self.tracker.get_active_session(line)
                current_key = f"{session}/{line[:10]}"
                if current_key != last_key:
                    origin = self.tracker.get_active_origin(
                        line, self.ident, session, self.config
                    )
                    last_key = current_key
            else:
                origin = default_origin

            sio.write(f"{line.strip()},{origin},{offset_before}\n")

        sio.seek(0)
        return sio, eof

    def process_resample(self, sio: StringIO) -> Tuple[pd.DataFrame, int]:
        """
        Resample a prepared batch into the target timeframe.

        Args:
            sio: StringIO buffer containing batch CSV data

        Returns:
            A tuple of:
            - Resampled DataFrame
            - Next input file position to resume from
        """
        df = pd.read_csv(sio, parse_dates=["time"], index_col="time")
        if df.empty:
            raise ValueError("Empty batch read from StringIO")

        resampled_list = []

        # Use the primary session's timeframe configuration
        session = next(iter(self.config.sessions.values()))
        tf_cfg = session.timeframes.get(self.ident)

        # Resample independently per origin
        for origin, origin_df in df.groupby('origin'):
            res = origin_df.resample(
                tf_cfg.rule,
                label=tf_cfg.label,
                closed=tf_cfg.closed,
                origin=origin
            ).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'offset': 'first'
            })

            # Drop empty or invalid bars
            res = res[res['volume'].gt(0) & res['volume'].notna()]
            resampled_list.append(res)

        # Combine all origins into a single DataFrame
        full_resampled = pd.concat(resampled_list).sort_index()

        # Determine resume offset from the last completed bar
        next_input_pos = int(full_resampled.iloc[-1]['offset'])

        # Final formatting
        full_resampled = (
            full_resampled
            .drop(columns=["offset"])
            .round(self.config.round_decimals)
        )
        full_resampled.index = full_resampled.index.strftime("%Y-%m-%d %H:%M:%S")

        return full_resampled, next_input_pos


class ResampleWorker:
    """
    Coordinates resampling across all configured timeframes for a symbol.
    """

    def __init__(self, symbol: str, app_config: AppConfig):
        """
        Initialize the worker for a given symbol.

        Args:
            symbol: Trading symbol
            app_config: Global application configuration
        """
        self.symbol = symbol
        self.app_config = app_config
        self.config = resample_get_symbol_config(symbol, app_config)
        self.data_path = Path(app_config.resample.paths.data)

    def run(self):
        """
        Execute resampling sequentially for all configured timeframes.
        """
        for ident in self.config.timeframes:
            try:
                engine = ResampleEngine(self.symbol, ident, self.config, self.data_path)

                # Root timeframes are pass-through only
                if engine.is_root:
                    continue

                self._execute_engine(engine)

            except (ValueError, IOError) as e:
                if VERBOSE:
                    print(f"  Skipping {ident} for {self.symbol}: {e}")
                continue

    def _execute_engine(self, engine: ResampleEngine):
        """
        Run the incremental resampling loop for a single engine.

        Args:
            engine: Initialized ResampleEngine instance
        """
        input_pos, output_pos = engine.read_index()

        with open(engine.input_path, "r") as f_in, open(engine.output_path, "r+") as f_out:
            # Read and possibly write header
            header = f_in.readline()

            if input_pos > 0:
                f_in.seek(input_pos)

            if output_pos == 0:
                f_out.write(header)
                output_pos = f_out.tell()

            # Process until EOF
            while True:
                sio, eof = engine.prepare_batch(f_in, header)
                resampled, next_in_pos = engine.process_resample(sio)

                # Rewrite output up to last confirmed position
                f_out.seek(output_pos)
                f_out.truncate(output_pos)
                f_out.write(resampled.iloc[:-1].to_csv(index=True, header=False))
                f_out.flush()

                # Persist index before writing final row
                output_pos = f_out.tell()
                engine.write_index(next_in_pos, output_pos)

                # Write trailing bar (kept open for next batch)
                f_out.write(resampled.tail(1).to_csv(index=True, header=False))

                if eof:
                    break

                f_in.seek(next_in_pos)


def fork_resample(args) -> bool:
    """
    Multiprocessing-friendly entry point for symbol resampling.

    Args:
        args: Tuple of (symbol, app_config)

    Returns:
        True on successful completion
    """
    symbol, config = args
    worker = ResampleWorker(symbol, config)
    worker.run()
    return True
