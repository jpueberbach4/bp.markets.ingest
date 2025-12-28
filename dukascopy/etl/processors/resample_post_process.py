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
    offset = step.offset

    # Iterate over each suffix that identifies rows to be merged
    for ends_with in step.ends_with:
        # Find all index positions ending with the given suffix
        positions = np.where(df.index.str.endswith(ends_with))[0]

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
                else:
                    # Offset definition is invalid; abort post-processing
                    raise PostProcessingError(
                        f"Post-processing error for {self.symbol} at timeframe {self.ident}"
                    )

        # Remove all rows that were merged for this suffix
        df = df[~df.index.str.endswith(ends_with)]

    return df
