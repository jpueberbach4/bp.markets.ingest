#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        aggregate.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Description: Conversion to OOP - Incremental OHLCV aggregation engine.

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
import pandas as pd
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
        """
        Initialize the aggregation engine.

        Args:
            symbol: Trading symbol to aggregate.
            app_config: Global application configuration.
        """
        # Set properties
        self.symbol = symbol
        self.config = config
        
        # Paths for index tracking and master output file
        self.index_path = Path(self.config.paths.data) / f"index/{self.symbol}.idx"
        self.output_path = Path(self.config.paths.data) / f"{self.symbol}.csv"

    def read_index(self) -> Tuple[date, int, int]:
        """
        Read the last processed date and file positions from the index file.

        Returns:
            Tuple containing:
            - Last processed date
            - Input file position
            - Output file position
        """
        try:
            if not self.index_path.exists():
                self.write_index(datetime.utcfromtimestamp(0).date(), 0, 0)
                return datetime.utcfromtimestamp(0).date(), 0, 0
            
            with open(self.index_path, 'r') as f_idx:
                lines = f_idx.readlines()[:3]
                date_str, in_pos, out_pos = [line.strip() for line in lines]
                return datetime.strptime(date_str, "%Y-%m-%d").date(), int(in_pos), int(out_pos)

        except (ValueError, IndexError) as e:
            raise IndexCorruptionError(f"Corrupt index at {self.index_path}. Check for partial writes.") from e

    def write_index(self, dt: date, input_pos: int, output_pos: int):
        """
        Atomically write the last processed date and file positions to the index file.

        Args:
            dt: Last processed date.
            input_position: Input file position after reading.
            output_position: Output file position after writing.
        """
        if input_pos < 0 or output_pos < 0:
            raise IndexValidationError(
                f"Invalid offsets for {self.symbol}: IN={input_pos}, OUT={output_pos}"
            )
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

    def _resolve_input_path(self, dt: date) -> Path:
        """
        Determine the path to the daily CSV file for a given date.

        Args:
            dt: Date to resolve.

        Returns:
            Path to the CSV file.
        """
        path = Path(self.config.paths.historic) / f"{dt.year}/{dt.month:02}/{self.symbol}_{dt:%Y%m%d}.csv"
        if not path.exists():
            path = Path(self.config.paths.live) / f"{self.symbol}_{dt:%Y%m%d}.csv"
        return path

    def process_date(self, dt: date) -> bool:
        """
        Aggregate a single day of data into the master CSV file.

        Args:
            dt: Date to process.

        Returns:
            True if processing was successful, False otherwise.
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
        """
        Initialize the aggregation worker.

        Args:
            symbol: Trading symbol.
            dates: List of dates to process.
            app_config: Global application configuration.
        """
        # Set properties
        self.app_config = app_config
        self.config = app_config.aggregate
        self.dates = dates

        # Initialize engine
        self.engine = AggregateEngine(symbol, self.config)

    def run(self) -> bool:
        """
        Sequentially process all assigned dates.

        Returns:
            True if all dates processed successfully.
        """
        # For each date
        for dt in self.dates:
            # Process date using engine
            self.engine.process_date(dt)

        return True


def fork_aggregate(args: Tuple[str, List[date], AppConfig]) -> bool:
    """
    Multiprocessing-friendly entry point.

    Args:
        args: Tuple containing (symbol, list of dates, app_config).

    Returns:
        True if aggregation completed successfully.
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
