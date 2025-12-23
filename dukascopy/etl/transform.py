#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        transform.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Updated:     2025-12-23
              Strengthening of code
              - Optional OHLCV validation
              - Optional fsync
              - Custom exceptions for better traceability

 Description: Transform Dukascopy Historical JSON delta
              format into normalized OHLC CSV files. Supports vectorized
              computation, multiprocessing, and progress tracking.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - orjson

 License:
     MIT License
===============================================================================
"""
import pandas as pd
import numpy as np
import orjson
import os
from datetime import date
from pathlib import Path
from typing import Tuple

from dst import get_symbol_time_shift_ms
from config.app_config import AppConfig, TransformConfig, TransformSymbolProcessingStep
from exceptions import *

class TransformEngine:
    """
    Handles the vectorized core logic of reconstructing OHLCV data from
    Dukascopy JSON delta formats.
    """

    def __init__(self, dt: date, symbol: str, config: TransformConfig):
        """Initialize the transform engine with symbol-, date-, and config context.

        Args:
            dt (date): Trading date associated with the transformation.
            symbol (str): Trading symbol being processed.
            config (TransformConfig): Transform-related configuration values.
        """
        # Set properties
        self.symbol = symbol
        self.dt = dt
        self.config = config

    def _apply_post_processing(self, df: pd.DataFrame, step: TransformSymbolProcessingStep) -> pd.DataFrame:
        """Apply a symbol-specific post-processing step to an OHLCV DataFrame.

        Supported actions include:
        - ``multiply``: Multiply a target column by a scalar value and round the
        result according to the configured precision.
        - ``validate``: Perform logical integrity checks on OHLC price data
        (e.g., high/low bounds and non-negative prices). Validation errors are
        currently logged but do not interrupt processing.

        Args:
            df (pd.DataFrame): The OHLCV DataFrame to post-process.
            step (TransformSymbolProcessingStep): Definition of the post-processing
                step, including the action type, target column (if applicable),
                and associated parameters.

        Returns:
            pd.DataFrame: The DataFrame after the post-processing step has been
            applied. For validation steps, the input DataFrame is returned unchanged.

        Raises:
            TransformLogicError: If the specified post-processing action is not supported.
            ProcessingError: If a required target column is missing during a
                column-based transformation.
        """
        # Validate that the requested action is supported
        if step.action not in ["multiply", "validate"]:
            raise TransformLogicError(f"Unsupported transform action: {step.action}")

        # Apply multiplication transformation
        if step.action == "multiply":
            # Ensure the target column exists before modifying it
            if step.column in df.columns:
                # Convert column to float and multiply by the provided value
                df[step.column] = df[step.column].astype(np.float64) * step.value
                # Round to stay compliant with settings
                df[step.column] = np.round(df[step.column], self.config.round_decimals)
            else:
                # Raise an error if the column is missing
                raise ProcessingError(
                    f"Symbol {self.symbol}, Column '{step.column}' not found during {step.action} step"
                )

        if step.action == "validate":
            try:
                # Logical checks for OHLC integrity
                errors = []
                if not (df['high'] >= df['low']).all():
                    errors.append("High price below Low price")
                if not (df['high'] >= df[['open', 'close']].max(axis=1)).all():
                    errors.append("High price below Open or Close")
                if not (df['low'] <= df[['open', 'close']].min(axis=1)).all():
                    errors.append("Low price above Open or Close")
                if (df[['open', 'high', 'low', 'close']] < 0).any().any():
                    errors.append("Negative prices detected")

                if errors:
                    # Raise your custom exception with details
                    raise DataValidationError(f"OHLC Integrity Failure: {', '.join(errors)}")

            except DataValidationError as e:
                # Todo, only log atm. Data is not flawless.
                print(f"Data validation error on {self.symbol} at date {self.dt}: {e}") 

        # Return the modified DataFrame
        return df


    def process_json(self, data: dict) -> pd.DataFrame:
        """Convert a Dukascopy delta-encoded JSON payload into an OHLCV DataFrame.

        This method reconstructs timestamps and OHLC prices using cumulative
        delta calculations, applies symbol- and date-specific time shifts
        (e.g., DST handling), filters out non-trading candles, rounds prices
        according to configuration, and applies symbol-specific post-processing
        steps. If validation is enabled in the configuration, OHLC integrity
        checks are injected dynamically into the post-processing pipeline.

        All operations are vectorized for performance.

        Args:
            data (dict): Parsed Dukascopy JSON payload containing delta-encoded
                market data fields (e.g., times, opens, highs, lows, closes,
                volumes, multipliers, and timestamps).

        Returns:
            pd.DataFrame: A normalized OHLCV DataFrame with the following columns:
                ['time', 'open', 'high', 'low', 'close', 'volume'].

        Raises:
            ProcessingError: If the JSON schema is malformed, required fields are
                missing, or an unexpected error occurs during transformation.
            TransformLogicError: If an unsupported post-processing action is
                encountered.
            DataValidationError: If OHLC validation fails and validation errors
                are propagated by configuration.
        """
        try:
            # Resolve symbol- and date-specific timestamp shift (e.g. DST handling)
            time_shift_ms = get_symbol_time_shift_ms(self.dt, self.symbol, self.config)
            try:
                # Reconstruct timestamps using cumulative deltas
                times = (
                    np.cumsum(np.array(data["times"], dtype=np.int64) * data["shift"])
                    + (data["timestamp"] + time_shift_ms)
                )

                # Reconstruct OHLC values using cumulative delta math
                opens = data["open"] + np.cumsum(
                    np.array(data["opens"], dtype=np.float64) * data["multiplier"]
                )
                highs = data["high"] + np.cumsum(
                    np.array(data["highs"], dtype=np.float64) * data["multiplier"]
                )
                lows = data["low"] + np.cumsum(
                    np.array(data["lows"], dtype=np.float64) * data["multiplier"]
                )
                closes = data["close"] + np.cumsum(
                    np.array(data["closes"], dtype=np.float64) * data["multiplier"]
                )

                # Volume is absolute, not delta-based
                volumes = np.array(data["volumes"], dtype=np.float64)
            
            except KeyError as e:
                raise ProcessingError(f"Malformed JSON schema for {self.symbol}: missing key {e}")

            # Filter out zero-volume candles (gaps / non-trading periods)
            mask = volumes != 0.0

            # Apply mask consistently across all arrays
            t_f, o_f, h_f, l_f, c_f, v_f = [
                arr[mask] for arr in [times, opens, highs, lows, closes, volumes]
            ]

            # Convert UNIX milliseconds to ISO datetime strings in batch
            time_strings = [
                str(t).replace("T", " ")[:19]
                for t in np.array(t_f * 1_000_000, dtype="datetime64[ns]")
            ]

            # Assemble final DataFrame and apply price rounding
            full_transformed = pd.DataFrame(
                {
                    "time": time_strings,
                    "open": np.round(o_f, self.config.round_decimals),
                    "high": np.round(h_f, self.config.round_decimals),
                    "low": np.round(l_f, self.config.round_decimals),
                    "close": np.round(c_f, self.config.round_decimals),
                    "volume": v_f,
                }
            )

            # Get symbol specific configuration
            sym_cfg = self.config.symbols.get(self.symbol) if self.config.symbols else None
            
            # Determine post-processing steps
            steps = []
            if sym_cfg and sym_cfg.post:
                # Convert dicts to Dataclasses if they aren't already
                steps = [
                    TransformSymbolProcessingStep(**s) if isinstance(s, dict) else s 
                    for s in sym_cfg.post.values()
                ]

            # Inject the validation step dynamically if the flag is enabled
            if self.config.validate:
                steps.append(TransformSymbolProcessingStep(action="validate"))

            # Apply post-processing
            for step in steps:
                full_transformed = self._apply_post_processing(full_transformed, step)

            # Return dataframe
            return full_transformed

        except (DataValidationError, ProcessingError, TransformLogicError):
            raise
        except Exception as e:
            raise ProcessingError(f"Vectorized transformation failed for {symbol}: {e}") from e


class TransformWorker:
    """
    Handles file path resolution, environment cleanup (Live vs Historic),
    and atomic file writing.
    """

    def __init__(self, dt: date, symbol: str, app_config: AppConfig):
        """Initialize a transform worker for a specific symbol and trading date.

        This constructor binds the worker to a single trading date and symbol,
        extracts transform-related configuration, and initializes the underlying
        transform engine used to process market data.

        Args:
            dt (date): Trading date associated with this worker instance.
            symbol (str): Trading symbol to be processed.
            app_config (AppConfig): Global application configuration containing
                transform and path settings.
        """
        # Set properties
        self.app_config = app_config
        self.config = app_config.transform
        self.symbol = symbol
        self.dt = dt
        # Create engine instance
        self.engine = TransformEngine(dt, symbol, self.config)

    def resolve_paths(self) -> Tuple[Path, Path]:
        """Resolve source JSON and target CSV paths for the worker's symbol and date.

        This method prefers historical data when available. If a historical JSON
        file exists, any corresponding live JSON and CSV files are removed to
        prevent duplicates or stale data. If historical data is not present,
        the method falls back to live data paths.

        Returns:
            Tuple[Path, Path]: A tuple containing:
                - Path to the source JSON file.
                - Path to the target CSV file.

        Raises:
            DataNotFoundError: If neither a historical nor live JSON source file
                exists for the worker's symbol and date.
        """
        # Historical cache and output paths
        hist_cache = (
            Path(self.config.paths.historic)
            / self.dt.strftime(f"%Y/%m/{self.symbol}_%Y%m%d.json")
        )
        hist_data = (
            Path(self.config.paths.data)
            / self.dt.strftime(f"%Y/%m/{self.symbol}_%Y%m%d.csv")
        )

        # Live cache and output paths
        live_cache = (
            Path(self.config.paths.live)
            / self.dt.strftime(f"{self.symbol}_%Y%m%d.json")
        )
        live_data = (
            Path(self.config.paths.live)
            / self.dt.strftime(f"{self.symbol}_%Y%m%d.csv")
        )

        # Prefer historical data when available
        if hist_cache.is_file():
            live_cache.unlink(missing_ok=True)
            live_data.unlink(missing_ok=True)
            return hist_cache, hist_data

        # Fallback to live data if historical not present
        if live_cache.is_file():
            return live_cache, live_data

        # No source data available
        raise DataNotFoundError(f"No JSON source found for {symbol} on {dt}")

    def run(self) -> bool:
        """Execute the end-to-end transformation pipeline for the worker's symbol and date.

        This method performs the following steps:
        1. Resolves input JSON and target CSV paths (preferring historical data).
        2. Loads the source JSON payload.
        3. Transforms delta-encoded market data into normalized OHLCV format.
        4. Applies symbol-specific post-processing and optional validation.
        5. Writes the resulting DataFrame to disk using an atomic file replacement
        strategy, optionally syncing to disk if configured.

        Returns:
            bool: True if the transformation and write completed successfully.

        Raises:
            DataNotFoundError: If no source JSON file exists for the worker's symbol
                and date.
            ProcessingError: If the JSON payload cannot be transformed into
                normalized OHLCV data.
            TransactionError: If a disk I/O error occurs during writing, or if an
                unexpected runtime error occurs during processing.
        """
        try:
            # Resolve source JSON and target CSV paths
            source_path, target_path = self.resolve_paths()

            # Load JSON payload
            with open(source_path, "rb") as file:
                data = orjson.loads(file.read())

            # Transform raw deltas into normalized OHLCV data
            df = self.engine.process_json(data)

            # Ensure output directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file, then replace
            temp_path = target_path.with_suffix(".tmp")

            with open(temp_path, "w", encoding="utf-8", newline="") as f:
                # Write the dataframe to the file handle
                df.to_csv(f, index=False, header=True, sep=",")
                # Flush to OS
                f.flush()
                # Force flush to disk
                if self.config.fsync:
                    os.fsync(f.fileno())

            os.replace(temp_path, target_path)

            return True

        except (DataNotFoundError, ProcessingError):
            raise
        except OSError as e:
            raise TransactionError(f"Disk I/O failure writing {self.symbol}: {e}")
        except Exception as e:
            raise TransactionError(f"Unexpected worker failure for {self.symbol}: {e}")


def fork_transform(args: tuple) -> bool:
    """Multiprocessing-safe entry point for running a transformation job.

    Designed for use with multiprocessing pools, this function initializes
    a `TransformWorker` for a specific symbol and trading date using the
    provided application configuration, then executes the full transformation
    pipeline.

    Args:
        args (tuple): A tuple containing:
            - symbol (str): Trading symbol to process.
            - dt (date): Trading date associated with the job.
            - app_config (AppConfig): Application configuration used to
              initialize the worker.

    Returns:
        bool: True if the transformation pipeline completes successfully.

    Raises:
        ForkProcessError: If any exception occurs during worker initialization
            or execution within the forked process. The original traceback
            is printed before raising this exception.
    """
    try:
        symbol, dt, app_config = args
        # Initialize the worker
        worker = TransformWorker(dt, symbol, app_config)
        
        # Execute the worker
        return worker.run()
    
    except Exception as e:   
        raise ForkProcessError(f"Error on transform fork for {symbol}: {e}") from e


    