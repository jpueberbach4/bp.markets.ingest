#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        rexample_post_process.py
 Author:      JP Ueberbach
 Created:     2025-12-28 (moved from transform)
 Updated:     2026-02-12
 Description: Symbol-level post-processing and validation engine for OHLCV data.

              This module implements the rule-based transformation layer applied
              after raw OHLCV normalization. It provides deterministic,
              vectorized post-processing operations including arithmetic
              adjustments and integrity validation of price data.

              The engine is optimized for large time-series datasets and
              minimizes computational overhead through:

                  - O(1) full-window short-circuit checks
                  - O(log N) boundary resolution via index.searchsorted
                  - Integer-based slicing instead of boolean masking
                  - Slice-local validation to avoid full DataFrame scans

              Transformations are defined via TransformSymbolProcessingStep
              configuration objects and executed sequentially.

              Supported operations:
                  - Arithmetic column adjustments (add, subtract, multiply, divide)
                  - OHLC structural validation (high/low consistency, negativity checks)

              Validation failures are reported via structured exceptions but may
              be soft-logged depending on configuration.

              This module is intentionally stateless and side-effect limited,
              making it safe for high-throughput batch pipelines and parallel
              execution contexts.

 Usage:
     Imported and invoked by the transformation pipeline.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy

 License:
     MIT License
===============================================================================
"""
from etl.exceptions import *
from etl.config.app_config import *
import pandas as pd
import numpy as np

def _transform_post_process(
    o,
    df: pd.DataFrame,
    step: TransformSymbolProcessingStep
) -> pd.DataFrame:
    """
    Apply a single post-processing transformation or validation step.

    Supports:
        - Arithmetic adjustments (add, subtract, multiply, divide)
        - OHLC integrity validation

    Optimizations:
        - O(1) full-range short-circuit
        - O(log N) boundary lookup via searchsorted
        - Integer slicing instead of boolean masks (avoids O(N) scans)

    Complexity:
        - Boundary resolution: O(log N)
        - Arithmetic transform: O(K × R)
        - Validation: O(R)

        Where:
            N = total rows in df
            R = rows in affected slice
            K = number of columns in step.columns

        Worst case: O(N)
    """

    # Guard: if DataFrame empty, nothing to do (constant time → O(1))
    if df.empty:
        return df

    # Extract rule boundaries safely from step object (O(1))
    from_date = getattr(step, 'from_date', None)
    to_date = getattr(step, 'to_date', None)

    # Convert boundary strings to timestamps if provided (object creation → O(1))
    rule_start = pd.to_datetime(from_date) if from_date else None
    rule_end = pd.to_datetime(to_date) if to_date else None

    # O(1) full-window short-circuit:
    # If dataset lies completely outside rule window, skip entire step.
    if rule_start or rule_end:
        data_start = df.index[0]     # First timestamp (O(1))
        data_end = df.index[-1]      # Last timestamp (O(1))

        if (rule_end and data_start > rule_end) or \
           (rule_start and data_end < rule_start):
            return df  # No overlap → no work

    # Default slice covers full DataFrame (O(1))
    start_idx = 0
    end_idx = len(df)

    # Use binary search to find left boundary (O(log N))
    if rule_start:
        start_idx = df.index.searchsorted(rule_start, side='left')

    # Use binary search to find right boundary (O(log N))
    if rule_end:
        end_idx = df.index.searchsorted(rule_end, side='right')

    # If slice empty after boundary resolution → skip (O(1))
    if start_idx >= end_idx:
        return df

    # ----------------------------------------------------------
    # Arithmetic transformations
    # ----------------------------------------------------------

    if step.action in ["add", "subtract", "multiply", "divide", "+", "-", "*", "/"]:

        # Loop through each target column (K iterations)
        for column in step.columns:

            # Fail fast if column missing (O(1))
            if column not in df.columns:
                raise ProcessingError(
                    f"Symbol {o.symbol}, Column '{column}' not found during {step.action} step"
                )

            # Convert entire column to float64 to ensure safe math ops (O(N))
            series = df[column].astype(np.float64)

            # Slice only affected rows (view via iloc → O(R))
            target = series.iloc[start_idx:end_idx]

            # Perform correct vectorized math operation (O(R))
            if step.action in ["*", "multiply"]:
                result = target * step.value

            elif step.action in ["+", "add"]:
                result = target + step.value

            elif step.action in ["-", "subtract"]:
                result = target - step.value

            elif step.action in ["/", "divide"]:
                result = target / step.value

            # Write result back into original DataFrame using integer position
            # Avoids label-based alignment overhead (O(R))
            df.iloc[
                start_idx:end_idx,
                df.columns.get_loc(column)
            ] = np.round(result, o.config.round_decimals)

    # ----------------------------------------------------------
    # OHLC validation
    # ----------------------------------------------------------

    if step.action == "validate":
        try:
            # Slice only relevant portion for validation (O(R))
            v_df = df.iloc[start_idx:end_idx]

            errors = []

            # High must be >= Low (vectorized comparison → O(R))
            if not (v_df['high'] >= v_df['low']).all():
                errors.append("High price below Low price")

            # High must be >= max(Open, Close) per row (O(R))
            if not (
                v_df['high'] >= v_df[['open', 'close']].max(axis=1)
            ).all():
                errors.append("High price below Open or Close")

            # Low must be <= min(Open, Close) per row (O(R))
            if not (
                v_df['low'] <= v_df[['open', 'close']].min(axis=1)
            ).all():
                errors.append("Low price above Open or Close")

            # No negative prices allowed (O(R))
            if (v_df[['open', 'high', 'low', 'close']] < 0).any().any():
                errors.append("Negative prices detected")

            # If any validation rule failed → raise structured error
            if errors:
                raise DataValidationError(
                    f"OHLC Integrity Failure: {', '.join(errors)}"
                )

        except DataValidationError as e:
            # Log but do NOT crash entire pipeline (intentional soft-fail)
            print(f"Data validation error on {o.symbol} at date {o.dt}: {e}")

    # Return possibly modified DataFrame
    return df
