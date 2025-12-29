#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        rexample_post_process.py
 Author:      JP Ueberbach
 Created:     2025-12-28
 Description: Post-processing utilities for resampled OHLCV data.

              This module contains logic used after resampling symbol-level
              time series data. It performs structural fixes and merges
              intermediate rows into their correct anchor rows based on
              predefined offsets. The primary use case is producing
              Panama-adjusted views and other higher-timeframe aggregates
              efficiently and safely.

 Usage:
     Imported and invoked by the resampling pipeline.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy

 License:
     MIT License
===============================================================================
"""
import pandas as pd
import numpy as np


def resample_post_process_range_mask(df: pd.DataFrame, step) -> pd.Series:
    # Setup the mask to contain everything
    mask = pd.Series(True, index=df.index)
    
    # Convert index to datetime if it's currently strings for comparison
    ts_index = pd.to_datetime(df.index)

    if step.from_date:
        mask &= (ts_index >= pd.to_datetime(step.from_date))
    if step.to_date:
        mask &= (ts_index <= pd.to_datetime(step.to_date))
    if step.weekdays:
        mask &= ts_index.dayofweek.isin(step.weekdays)

    # And... return it
    return mask

def resample_post_process_merge(df: pd.DataFrame, ident: str, step, config) -> pd.DataFrame:
    """Post-process a resampled DataFrame by merging selected rows into anchor rows.

    This function identifies rows whose index ends with specific suffixes and merges
    their OHLCV data into corresponding anchor rows determined by a fixed offset.
    After merging, the source rows are removed from the DataFrame.

    Args:
        df (pd.DataFrame): Resampled OHLCV data indexed by string-based timestamps
            or identifiers.
        ident (str): Timeframe or identifier used for error reporting.
        step: Configuration object defining merge behavior. Must provide:
            - offset (int): Relative position of the anchor row to merge into.
            - ends_with (Iterable[str]): Index suffixes identifying rows to merge.
        config: Additional configuration object (currently unused).

    Returns:
        pd.DataFrame: The post-processed DataFrame with merged rows removed.

    Raises:
        PostProcessingError: If the computed anchor position is out of bounds.
    """

    # Get the limiting mask for this step
    mask = resample_post_process_range_mask(df, step)

    # Get the offset
    offset = step.offset

    # Setup positions array of idx to get dropped
    drop_positions = []

    # Iterate over each suffix that identifies rows to be merged
    for ends_with in step.ends_with:

        # Select franken candles, combine with previous calculated mask
        _mask = df.index.str.endswith(ends_with) & mask.values

        # Get the positions where the mask is valid
        positions = np.where(_mask)[0]

        # Merge each selected row into its corresponding anchor row
        for pos in positions:
            if pos > 0:
                anchor_pos = pos + offset

                # Ensure the anchor position exists in the DataFrame
                if 0 <= anchor_pos < len(df):
                    select_idx = df.index[pos]
                    anchor_idx = df.index[anchor_pos]

                    # Merge OHLCV values into the anchor row
                    df.at[anchor_idx, 'high'] = max(
                        df.at[anchor_idx, 'high'],
                        df.at[select_idx, 'high'],
                    )
                    df.at[anchor_idx, 'low'] = min(
                        df.at[anchor_idx, 'low'],
                        df.at[select_idx, 'low'],
                    )
                    df.at[anchor_idx, 'close'] = df.at[select_idx, 'close']
                    df.at[anchor_idx, 'volume'] += df.at[select_idx, 'volume']

                    drop_positions.append(select_idx)
                else:
                    # Offset definition is invalid; abort post-processing
                    raise PostProcessingError(
                        f"Post-processing error at timeframe {ident}"
                    )

    # Remove all rows that were merged for this suffix
    if drop_positions:
        # Drop selected rows
        df = df.drop(index=list(set(drop_positions)))

    return df
