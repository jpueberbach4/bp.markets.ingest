#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        transform.py
 Author:      JP Ueberbach
 Created:     2025-12-19
 Description: Conversion to OOP - Transform Dukascopy Historical JSON delta
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
from config.app_config import AppConfig, TransformConfig, TransformSymbolProcessingStep, load_app_config
from dataclasses import asdict
import yaml


class TransformEngine:
    """
    Handles the vectorized core logic of reconstructing OHLCV data from
    Dukascopy JSON delta formats.
    """

    def __init__(self, config: TransformConfig):
        """
        Initializes the transform engine.

        Args:
            config (TransformConfig): Transform-related configuration values.
        """
        self.config = config

    def _apply_post_processing(self, df: pd.DataFrame, step: TransformSymbolProcessingStep) -> pd.DataFrame:
        """Apply post-processing transformations to a DataFrame column.

        Currently supports multiplying a specified column by a scalar value.

        Args:
            df (pd.DataFrame): Input DataFrame to be transformed.
            step (TransformSymbolProcessingStep): Transformation step defining
                the action to apply, the target column, and the value to use.

        Returns:
            pd.DataFrame: The transformed DataFrame.

        Raises:
            ValueError: If the transformation action is not supported.
            KeyError: If the specified column does not exist in the DataFrame.
        """
        # Validate that the requested action is supported
        if step.action not in ["multiply"]:
            raise ValueError(f"Step action {step.action} for transform unsupported")

        # Apply multiplication transformation
        if step.action == "multiply":
            # Ensure the target column exists before modifying it
            if step.column in df.columns:
                # Convert column to float and multiply by the provided value
                df[step.column] = df[step.column].astype(float) * step.value
            else:
                # Raise an error if the column is missing
                raise KeyError(
                    f"Step action {step.action} for transform, column '{step.column}' not found in DataFrame"
                )

        # Return the modified DataFrame
        return df


    def process_json(self, data: dict, dt: date, symbol: str) -> pd.DataFrame:
        """
        Converts a Dukascopy JSON delta payload into a normalized OHLCV DataFrame.

        This method reconstructs OHLC values using cumulative delta math,
        applies symbol-specific time shifts, filters invalid candles, and
        formats timestamps in a vectorized manner for performance.

        Args:
            data (dict): Parsed JSON payload containing delta-encoded market data.
            dt (date): Trading date associated with the data.
            symbol (str): Trading symbol being processed.

        Returns:
            pandas.DataFrame: Normalized OHLCV data with columns:
                ['time', 'open', 'high', 'low', 'close', 'volume'].
        """
        try:
            # Resolve symbol- and date-specific timestamp shift (e.g. DST handling)
            time_shift_ms = get_symbol_time_shift_ms(dt, symbol, self.config)

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

            # Apply post-processing
            if self.config.symbols:
                sym_cfg = self.config.symbols.get(symbol)
                if sym_cfg and sym_cfg.post:
                    for sym_step in sym_cfg.post.values():
                        # This is dirty. YAML config loading to correct dataclasses is an utterly hell in python
                        # Todo: check if there is a default project which simplifies this to dataclass loading
                        #       otherwise, perhaps second project?
                        if isinstance(sym_step, dict):
                            sym_step = TransformSymbolProcessingStep(**sym_step)

                        full_transformed = self._apply_post_processing(full_transformed, sym_step)

            # Return dataframe
            return full_transformed

        except Exception as e:
            # Explicitly propagate
            raise e


class TransformWorker:
    """
    Handles file path resolution, environment cleanup (Live vs Historic),
    and atomic file writing.
    """

    def __init__(self, app_config: AppConfig):
        """
        Initializes the transform worker.

        Args:
            app_config (AppConfig): Global application configuration.
        """
        self.app_config = app_config
        self.config = app_config.transform
        self.engine = TransformEngine(self.config)

    def resolve_paths(self, symbol: str, dt: date) -> Tuple[Path, Path]:
        """
        Resolves source JSON and target CSV paths for a symbol and date.

        Prefers historical data when available and automatically removes
        redundant live files once historical data arrives.

        Args:
            symbol (str): Trading symbol.
            dt (date): Trading date.

        Returns:
            Tuple[Path, Path]: Source JSON path and target CSV path.

        Raises:
            FileNotFoundError: If no JSON source file exists.
        """
        # Historical cache and output paths
        hist_cache = (
            Path(self.config.paths.historic)
            / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.json")
        )
        hist_data = (
            Path(self.config.paths.data)
            / dt.strftime(f"%Y/%m/{symbol}_%Y%m%d.csv")
        )

        # Live cache and output paths
        live_cache = (
            Path(self.config.paths.live)
            / dt.strftime(f"{symbol}_%Y%m%d.json")
        )
        live_data = (
            Path(self.config.paths.live)
            / dt.strftime(f"{symbol}_%Y%m%d.csv")
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
        raise FileNotFoundError(f"No JSON source found for {symbol} on {dt}")

    def run(self, symbol: str, dt: date) -> bool:
        """
        Executes the full transformation pipeline for a single symbol and date.

        Args:
            symbol (str): Trading symbol.
            dt (date): Trading date.

        Returns:
            bool: True if transformation succeeded, False otherwise.
        """
        try:
            # Resolve source JSON and target CSV paths
            source_path, target_path = self.resolve_paths(symbol, dt)

            # Load JSON payload
            with open(source_path, "rb") as file:
                data = orjson.loads(file.read())

            # Transform raw deltas into normalized OHLCV data
            df = self.engine.process_json(data, dt, symbol)

            # Ensure output directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file, then replace
            temp_path = target_path.with_suffix(".tmp")
            df.to_csv(temp_path, index=False, header=True, sep=",")
            os.replace(temp_path, target_path)

            return True

        except Exception:
            # Explicitly propagate
            raise e


def fork_transform(args: tuple) -> bool:
    """
    Multiprocessing-friendly entry point for running transformations.

    Args:
        args (tuple): Tuple of (symbol, date, app_config).

    Returns:
        bool: True if processing succeeded, False otherwise.
    """
    symbol, dt, app_config = args
    worker = TransformWorker(app_config)
    return worker.run(symbol, dt)


    