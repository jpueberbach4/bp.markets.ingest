#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        transform.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Updated:     2025-12-23
              2026-02-12

 Description:
     High-performance transformation engine for converting Dukascopy
     delta-encoded historical JSON into normalized OHLCV datasets.

     This module provides a deterministic, vectorized reconstruction pipeline
     with optional post-processing, validation, multiprocessing support, and
     atomic disk persistence.

     Core responsibilities:

         • Reconstruct timestamps and OHLC values via cumulative deltas
         • Apply symbol- and date-specific time shifts (DST-aware)
         • Filter non-trading candles
         • Execute rule-based post-processing steps
         • Perform optional OHLC structural validation
         • Persist results using atomic write + optional fsync
         • Support multiprocessing-safe execution

     Design principles:

         - O(N) vectorized computation (no row-wise loops)
         - Strict exception boundaries for traceability
         - Atomic writes to prevent partial/corrupt outputs
         - Stateless transform engine (safe for parallel execution)
         - Clear separation of:
               TransformEngine  → computation
               TransformWorker  → I/O + orchestration
               fork_transform   → multiprocessing boundary

     Complexity characteristics:

         Let:
             N = number of candles
             M = active post-processing rules
             K = number of derived aliases

         Per alias:
             - Reconstruction:        O(N)
             - Post-processing:       O(N × M) (optimized)
             - Disk write:            O(N)

         Overall dominant cost:       O(N)

     This module is designed for high-throughput batch pipelines and
     large-scale historical processing workloads.

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
from etl.config.app_config import AppConfig, TransformConfig, TransformSymbolProcessingStep

from etl.io.protocols import *
from etl.io.resample.factory import *
from etl.exceptions import *

from etl.processors.transform_post_process import _transform_post_process

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

    def process_json(self, data: dict, alias=None) -> pd.DataFrame:
        """
        Transform Dukascopy delta-encoded JSON payload into normalized OHLCV DataFrame.

        Pipeline:
            1. Apply symbol/date-specific time shift.
            2. Reconstruct timestamps via cumulative deltas.
            3. Reconstruct OHLC prices via cumulative deltas.
            4. Filter zero-volume candles.
            5. Assemble pandas DataFrame and round prices.
            6. Select relevant post-processing steps.
            7. Execute active steps (including optional validation).

        Complexity:
            - Timestamp reconstruction: O(N)
            - OHLC reconstruction: O(N)
            - Zero-volume filtering: O(N)
            - Rule pruning: O(M) with O(1) boundary checks
            - Post-processing execution: O(N × active_steps)

            Overall dominant cost: O(N)

            Where:
                N = number of candles
                M = number of configured post-processing rules

        Args:
            data (dict): Parsed JSON containing delta-encoded market data.
            alias (str | None): Optional alias symbol override.

        Returns:
            pd.DataFrame: Normalized OHLCV DataFrame indexed by time.

        Raises:
            ProcessingError: If JSON schema malformed or transformation fails.
            TransformLogicError: If invalid post-processing action encountered.
            DataValidationError: If validation fails and propagation enabled.
        """
        try:
            # Get DST / symbol-specific timestamp shift (config lookup → O(1))
            time_shift_ms = get_symbol_time_shift_ms(self.dt, self.symbol, self.config)

            # Resolve effective symbol name (constant time → O(1))
            symbol = alias if alias is not None else self.symbol

            try:
                # Reconstruct timestamps via cumulative sum (vectorized → O(N))
                times = (
                    np.cumsum(np.array(data["times"], dtype=np.int64) * data["shift"])
                    + (data["timestamp"] + time_shift_ms)
                )

                # Reconstruct open prices (vectorized cumulative delta → O(N))
                opens = data["open"] + np.cumsum(
                    np.array(data["opens"], dtype=np.float64) * data["multiplier"]
                )

                # Reconstruct high prices (O(N))
                highs = data["high"] + np.cumsum(
                    np.array(data["highs"], dtype=np.float64) * data["multiplier"]
                )

                # Reconstruct low prices (O(N))
                lows = data["low"] + np.cumsum(
                    np.array(data["lows"], dtype=np.float64) * data["multiplier"]
                )

                # Reconstruct close prices (O(N))
                closes = data["close"] + np.cumsum(
                    np.array(data["closes"], dtype=np.float64) * data["multiplier"]
                )

                # Volumes are absolute, simple array conversion (O(N))
                volumes = np.array(data["volumes"], dtype=np.float64)

            except KeyError as e:
                raise ProcessingError(
                    f"Malformed JSON schema for {self.symbol}: missing key {e}"
                )

            # Create boolean mask to remove zero-volume candles (vectorized → O(N))
            mask = volumes != 0.0

            # Apply mask to all arrays in single pass (O(N))
            t_f, o_f, h_f, l_f, c_f, v_f = [
                arr[mask] for arr in [times, opens, highs, lows, closes, volumes]
            ]

            # Convert ms → ns for pandas index (vectorized multiplication → O(N))
            idx = pd.DatetimeIndex(t_f * 1_000_000, name="time")

            # Build DataFrame from arrays (O(N))
            full_transformed = pd.DataFrame(
                data={
                    "open": o_f,
                    "high": h_f,
                    "low": l_f,
                    "close": c_f,
                    "volume": v_f,
                },
                index=idx
            ).round(self.config.round_decimals)  # Vectorized rounding → O(N)

            # Get symbol-specific config block (dict lookup → O(1))
            sym_cfg = self.config.symbols.get(symbol) if self.config.symbols else None

            # Initialize list of active post-processing steps (O(1))
            active_steps = []

            # Precompute date boundaries ONCE (avoid repeated object creation → O(1))
            fmt = "%Y-%m-%d %H:%M:%S"
            s_start_str = (pd.Timestamp(self.dt) - pd.Timedelta(days=1)).strftime(fmt)
            s_end_str = (pd.Timestamp(self.dt) + pd.Timedelta(days=2)).strftime(fmt)

            # If symbol has post-processing rules configured
            if sym_cfg and sym_cfg.post:

                # Iterate rules (O(M) where M = number of rules)
                for s in sym_cfg.post.values():

                    # Extract raw boundary strings (O(1))
                    f_date_str = s.get('from_date')
                    t_date_str = s.get('to_date')

                    # ISO string comparison is lexicographically sortable → O(1)
                    # Avoids datetime parsing cost and object allocation
                    if t_date_str and t_date_str < s_start_str:
                        continue

                    if f_date_str and f_date_str > s_end_str:
                        continue

                    # Instantiate rule only if relevant (object creation → O(1))
                    step = (
                        TransformSymbolProcessingStep(**s)
                        if isinstance(s, dict)
                        else s
                    )

                    active_steps.append(step)

            # Optionally inject validation step (constant append → O(1))
            if self.config.validate:
                active_steps.append(
                    TransformSymbolProcessingStep(action="validate")
                )

            # Execute each active step (each may scan dataframe → O(N × active_steps))
            for step in active_steps:
                full_transformed = _transform_post_process(
                    full_transformed, step
                )

            # Explicitly free large arrays to reduce memory pressure (O(1))
            del times, opens, highs, lows, closes, volumes
            del t_f, o_f, h_f, l_f, c_f, v_f, mask, idx

            # Return final normalized dataframe
            return full_transformed

        except (DataValidationError, ProcessingError, TransformLogicError):
            raise
        except Exception as e:
            raise ProcessingError(
                f"Vectorized transformation failed for {symbol}: {e}"
            ) from e



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
        self.fsync = self.config.fsync
        self.fmode = self.config.fmode
        self.symbol = symbol
        self.dt = dt
        # Create engine instance
        self.engine = TransformEngine(dt, symbol, self.config)

    def resolve_paths(self, alias=None) -> Tuple[Path, Path]:
        """
        Resolve source JSON and target output paths for a given symbol/date.

        The method prefers historical cache data over live data.

        Resolution order:
            1. If historic JSON exists → use it and delete stale live artifacts.
            2. Else if live JSON exists → use live paths.
            3. Else → raise DataNotFoundError.

        Complexity:
            - Path construction: O(1)
            - File existence checks: O(1)
            - File deletions (if triggered): O(1)

            Overall: O(1)

        Args:
            alias (str | None): Optional alias symbol name. If None, uses self.symbol.

        Returns:
            Tuple[Path, Path]: (source_json_path, target_output_path)

        Raises:
            DataNotFoundError: If neither historic nor live JSON file exists.
        """

        # Use alias if provided, otherwise default to primary symbol (O(1))
        alias = alias if alias is not None else self.symbol

        # Determine correct file extension based on resample mode (factory lookup → O(1))
        extension = ResampleIOFactory.get_appropriate_extension(self.fmode)

        # Construct historic JSON source path (pure path arithmetic → O(1))
        hist_cache = (
            Path(self.config.paths.historic)
            / self.dt.strftime(f"%Y/%m/{self.symbol}_%Y%m%d.json")
        )

        # Construct historic output path (O(1))
        hist_data = (
            Path(self.config.paths.data)
            / self.dt.strftime(f"%Y/%m/{alias}_%Y%m%d{extension}")
        )

        # Construct live JSON source path (O(1))
        live_cache = (
            Path(self.config.paths.live)
            / self.dt.strftime(f"{self.symbol}_%Y%m%d.json")
        )

        # Construct live output path (O(1))
        live_data = (
            Path(self.config.paths.live)
            / self.dt.strftime(f"{alias}_%Y%m%d{extension}")
        )

        # Prefer historic data if file exists (filesystem metadata check → O(1))
        if hist_cache.is_file():

            # Delete possible stale live JSON (constant-time unlink if exists → O(1))
            live_cache.unlink(missing_ok=True)

            # Delete possible stale live output file (O(1))
            live_data.unlink(missing_ok=True)

            # Return historic source + historic output location
            return hist_cache, hist_data

        # If no historic file, check for live file (O(1))
        if live_cache.is_file():
            return live_cache, live_data

        # If neither exists, fail fast (constant time error path → O(1))
        raise DataNotFoundError(
            f"No JSON source found for {self.symbol} on {self.dt}"
        )


    def run(self) -> bool:
        """
        Execute the full transformation pipeline for a single symbol/date.

        This method:
            1. Resolves the correct source JSON file (historic preferred).
            2. Loads the JSON payload into memory.
            3. Determines all alias symbols derived from this source symbol.
            4. Runs the vectorized transformation for each alias.
            5. Writes results atomically to disk.

        Complexity:
            - Path resolution: O(1)
            - JSON load: O(file_size)
            - Alias discovery: O(K) where K = number of configured symbols
            - Transformation: O(N) per alias (vectorized) + O(N×M) if post-processing active
            - Disk write: O(N)

            Total per alias ≈ O(N) dominant

        Returns:
            bool: True if transformation and atomic write succeed.

        Raises:
            DataNotFoundError: If no source JSON exists.
            ProcessingError: If transformation fails.
            TransactionError: If disk I/O or unexpected runtime error occurs.
        """
        try:
            # Resolve correct input/output paths (constant-time path logic → O(1))
            source_path, target_path = self.resolve_paths()

            # Load entire JSON file into memory (linear in file size → O(N))
            data = orjson.loads(Path(source_path).read_bytes())

            # Start with primary symbol (constant time → O(1))
            aliasses = [self.symbol]

            # Discover derived symbols that use this symbol as source (scan config → O(K))
            for key in self.config.symbols.keys():
                if self.config.symbols.get(key).source == self.symbol:
                    aliasses.append(key)

            # Process each alias independently (loop size = number of aliases)
            for alias in aliasses:

                # Re-resolve paths for alias (still constant time → O(1))
                source_path, target_path = self.resolve_paths(alias=alias)

                # Heavy lifting happens here:
                # Vectorized reconstruction → O(N)
                # Post-processing (if enabled) → up to O(N×M)
                df = self.engine.process_json(data, alias=alias)

                # Ensure directory exists (filesystem check → effectively O(1))
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Create temporary file path for atomic write (O(1))
                temp_path = target_path.with_suffix(".tmp")

                # Get appropriate writer implementation (factory lookup → O(1))
                writer = ResampleIOFactory.get_writer(
                    temp_path,
                    self.fmode,
                    fsync=self.config.fsync
                )

                # Write full dataframe to disk (linear in rows → O(N))
                with writer:
                    writer.write_batch(df)  # Actual data write
                    writer.flush()          # Ensure OS buffer flush (fsync if enabled)

                # Atomic replace prevents partial/corrupt files (OS-level operation → O(1))
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


    