#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        aggregate.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Updated:     2025-12-23
              Strengthening of code
              - Optional fsync
              - Custom exceptions for better traceability
 Description: Incremental OHLCV aggregation engine.

              This module provides:
              - AggregateEngine: Handles incremental appending of daily CSVs 
                to a master symbol file with crash-safe index tracking.
              - AggregateWorker: Manages the aggregation lifecycle for a symbol 
                across a range of dates.

 Requirements:
     - Python 3.8+
     - Pandas
===============================================================================
"""
import os
from pathlib import Path
from datetime import date, datetime
from typing import Tuple, List

from config.app_config import AppConfig, AggregateConfig
from exceptions import *


class AggregateEngine:
    """
    Handles the low-level incremental aggregation of CSV data for a symbol.
    """

    def __init__(self, symbol: str, config: AggregateConfig):
        """Initialize the aggregation engine for a specific trading symbol.

        This constructor sets up symbol-specific configuration, as well as
        paths for index tracking and the master output CSV file.

        Args:
            symbol (str): Trading symbol to aggregate.
            config (AggregateConfig): Global aggregation configuration, including
                paths and other settings.
        """
        # Set properties
        self.symbol = symbol
        self.config = config
        
        # Paths for index tracking and master output file
        self.index_path = Path(self.config.paths.data) / f"index/{self.symbol}.idx"
        self.output_path = Path(self.config.paths.data) / f"{self.symbol}.csv"

    def read_index(self) -> Tuple[date, int, int]:
        """Read the last processed date and file positions from the index file.

        If the index file does not exist, it is initialized with a default date
        (Unix epoch) and zeroed positions.

        Returns:
            Tuple[date, int, int]: A tuple containing:
                - Last processed date (`date`)
                - Input file position (`int`)
                - Output file position (`int`)

        Raises:
            IndexCorruptionError: If the index file exists but cannot be parsed
                correctly due to missing lines, invalid formatting, or corrupt data.
        """
        try:
            # Check if idx file exists
            if not self.index_path.exists():
                # Create idx file
                self.write_index(datetime.utcfromtimestamp(0).date(), 0, 0)
                return datetime.utcfromtimestamp(0).date(), 0, 0
            
            # Read idx file
            with open(self.index_path, 'r') as f_idx:
                lines = f_idx.readlines()[:3]
                date_str, in_pos, out_pos = [line.strip() for line in lines]
                return datetime.strptime(date_str, "%Y-%m-%d").date(), int(in_pos), int(out_pos)

        except (ValueError, IndexError) as e:
            raise IndexCorruptionError(f"Corrupt index at {self.index_path}. Check for partial writes.") from e

    def write_index(self, dt: date, input_pos: int, output_pos: int):
        """Atomically write the last processed date and file positions to the index file.

        This method ensures that the index is written safely using a temporary file
        and atomic replacement. Optionally, it can force the data to disk if
        `fsync` is enabled in the configuration.

        Args:
            dt (date): Last processed date to record.
            input_pos (int): Input file position after reading.
            output_pos (int): Output file position after writing.

        Raises:
            IndexValidationError: If `input_pos` or `output_pos` are negative.
            OSError: If writing to disk or atomic replacement fails.
        """
        if input_pos < 0 or output_pos < 0:
            raise IndexValidationError(
                f"Invalid offsets for {self.symbol}: IN={input_pos}, OUT={output_pos}"
            )
            
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = Path(f"{self.index_path}.tmp")
            
            # Write state to idx file
            with open(temp_path, "w") as f:
                f.write(f"{dt:%Y-%m-%d}\n{input_pos}\n{output_pos}")
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

    def _resolve_input_path(self, dt: date) -> Path:
        """Resolve the input CSV file path for a given date.

        This method first checks for a historical CSV file in the configured
        historical path. If the file does not exist, it falls back to the live
        data path.

        Args:
            dt (date): The trading date for which to resolve the CSV path.

        Returns:
            Path: The resolved path to the CSV file, either historical or live.

        Notes:
            The method does not raise an exception if the file does not exist;
            it only constructs and returns the expected path.
        """
        path = Path(self.config.paths.historic) / f"{dt.year}/{dt.month:02}/{self.symbol}_{dt:%Y%m%d}.csv"
        if not path.exists():
            path = Path(self.config.paths.live) / f"{self.symbol}_{dt:%Y%m%d}.csv"
        
        return path

    def process_date(self, dt: date) -> bool:
        """Aggregate a single day of CSV data into the master output file.

        This method reads the daily CSV file for the given date, appends its
        contents to the master CSV while maintaining crash safety, updates
        the index file, and optionally forces data to disk using `fsync`.

        The method handles partial reads by resuming from the last recorded
        input and output positions, and writes the header if the master file
        is newly created.

        Args:
            dt (date): The trading date to process.

        Returns:
            bool: True if data for the date was successfully aggregated;
                False if the input file does not exist, is empty, or the
                date was already processed.

        Raises:
            TransactionError: If a disk I/O error occurs during reading, writing,
                or flushing to disk.
        """
        input_path = self._resolve_input_path(dt)
        if not input_path.exists():
            return False

        # Read Index
        date_from, input_position, output_position = self.read_index()

        if dt < date_from:
            # Already processed date, return
            return False

        if dt > date_from:
            # New date, start reading from beginning
            input_position = 0

        try:
            if not self.output_path.exists():
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
                self.output_path.touch()

            with open(self.output_path, "r+", encoding="utf-8") as f_out, \
                open(input_path, "r", encoding="utf-8") as f_in:

                # Read header
                header = f_in.readline()

                # We processed this file before, continue from last know position
                if input_position > 0:
                    f_in.seek(input_position)

                # Crash-safety: rewind output file to last committed position
                f_out.truncate(output_position)
                f_out.seek(output_position)

                # Write header when output is new file
                if output_position == 0:
                    f_out.write(header)
                
                # Slurp file contents
                data = f_in.read()
                if not data:
                    return False

                # Write the data
                f_out.write(data)
                # Flush to OS
                f_out.flush()
                # Force persist to disk
                if self.config.fsync:
                    os.fsync(f_out.fileno())
                
                # Update index after writing
                self.write_index(dt, f_in.tell(), f_out.tell())
        except OSError as e:
                raise TransactionError(f"I/O failure during aggregation of {self.symbol} for {dt}: {e}")

        return True


class AggregateWorker:
    """
    Orchestrates the aggregation process for a symbol across multiple dates.
    """

    def __init__(self, symbol: str, dates: List[date], app_config: AppConfig):
        """Initialize an aggregation worker for a given symbol and date range.

        This constructor sets up the worker with a list of dates to process,
        the global application configuration, and initializes the aggregation
        engine for the specified trading symbol.

        Args:
            symbol (str): Trading symbol to aggregate.
            dates (List[date]): List of trading dates to process.
            app_config (AppConfig): Global application configuration containing
                aggregation settings and paths.
        """
        # Set properties
        self.app_config = app_config
        self.config = app_config.aggregate
        self.dates = dates

        # Initialize engine
        self.engine = AggregateEngine(symbol, self.config)

    def run(self) -> bool:
        """Process all assigned trading dates sequentially using the aggregation engine.

        This method iterates over the worker's list of dates and aggregates
        each day's CSV data into the master output file.

        Returns:
            bool: True if all assigned dates were processed successfully.
        """

        try:
            # For each date
            for dt in self.dates:
                # Process date using engine
                self.engine.process_date(dt)

        except (IndexCorruptionError, TransactionError, Exception) as e:
            raise

        return True


def fork_aggregate(args: Tuple[str, List[date], AppConfig]) -> bool:
    """Multiprocessing-safe entry point for running an aggregation job.

    Designed for use with multiprocessing pools, this function initializes
    an `AggregateWorker` for a specific trading symbol and list of dates
    using the provided application configuration, then executes the
    aggregation pipeline.

    Args:
        args (Tuple[str, List[date], AppConfig]): A tuple containing:
            - symbol (str): Trading symbol to aggregate.
            - dates (List[date]): List of trading dates to process.
            - app_config (AppConfig): Global application configuration.

    Returns:
        bool: True if the aggregation pipeline completes successfully.

    Raises:
        ForkProcessError: If any exception occurs during worker initialization
            or execution within the forked process.
    """
    try:

        symbol, dates, app_config = args
        # Initialize worker
        worker = AggregateWorker(symbol, dates, app_config)
        # Execute worker
        return worker.run()

    except Exception as e:
        # Raise
        raise ForkProcessError(f"Error on aggregate fork for {symbol}") from e
