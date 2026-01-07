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

from etl.config.app_config import AppConfig, AggregateConfig
from etl.io.resample.factory import *
from etl.exceptions import *


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
        self.fmode = config.fmode

        # Get the extension
        extension = ResampleIOFactory.get_appropriate_extension(self.fmode)

        # Paths for index tracking and master output file
        self.index_path = Path(self.config.paths.data) / f"index/{self.symbol}.idx"
        self.output_path = Path(self.config.paths.data) / f"{self.symbol}{extension}"

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
        extension = ResampleIOFactory.get_appropriate_extension(self.fmode)
        path = Path(self.config.paths.historic) / f"{dt.year}/{dt.month:02}/{self.symbol}_{dt:%Y%m%d}{extension}"
        if not path.exists():
            path = Path(self.config.paths.live) / f"{self.symbol}_{dt:%Y%m%d}{extension}"
        
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

        # Initialize index reader
        index = ResampleIOFactory.get_index_handler(self.index_path, self.fmode, fsync=self.config.fsync)

        # Read the index
        date_int, input_position, output_position = index.read()

        # Convert into date object
        date_str = str(date_int)
        date_from = date(year=int(date_str[:4]), month=int(date_str[4:6]), day=int(date_str[6:8]))

        if dt < date_from:
            # Already processed date, return
            return False

        if dt > date_from:
            # New date, start reading from beginning
            input_position = 0

        try:
            # Bugfix for binary mode, if 0 filesize, we can't memmap file. Might be a weekend-day without data
            size = os.path.getsize(input_path)
            if size == 0:
                return False

            # Initialize IO
            reader = ResampleIOFactory.get_reader(input_path, self.fmode)
            writer = ResampleIOFactory.get_writer(self.output_path, self.fmode, fsync=self.config.fsync)

            with reader, writer:
                # We processed this file before, continue from last know position
                if input_position > 0:
                    reader.seek(input_position)

                # Initialize output position if this is the first write
                if output_position == 0:
                    output_position = writer.tell()

                # Crash-safety: rewind output file to last committed position
                writer.truncate(output_position)
                
                # Slurp file contents
                data = reader.read_raw()

                if not data:
                    print("nodata")
                    return False

                writer.seek(output_position)
                writer.write_raw(data)
                writer.flush()

                dt_int = int(dt.strftime('%Y%m%d'))

                index.write(reader.tell(), writer.tell(), dt_int)
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
