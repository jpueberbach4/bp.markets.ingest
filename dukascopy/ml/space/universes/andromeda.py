"""
===============================================================================
File:        milkyway.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of the MilkyWay universe within the ML space.

    MilkyWay manages:
        - Data ingestion and temporal boundaries
        - Initialization of Comets and Normalizers
        - Feature and target preprocessing
        - BigBang normalization applying multiple Normalizers
        - Auditing of string-polluted and NaN dimensions
        - Ejection of payloads to Comets (models, gene dumps, logs)

Key Capabilities:
    - Config-driven universe instantiation
    - Cosmic normalization pipeline (Redshift, Kinematics)
    - Statistical auditing and reporting
    - Integration with Comet and Normalizer factories
===============================================================================
"""

import fnmatch
import pandas as pd
import numpy as np

from util.api import get_data
from ml.space.space import Universe

class Andromeda(Universe):
    """Concrete Universe class handling data ingestion and normalization."""

    def ignite(self, options=None):
        """Load raw data, handle targets, and filter features.

        Args:
            after_ms (int): Start timestamp in milliseconds.
            until_ms (int): End timestamp in milliseconds.
            limit (int): Maximum number of records to load.
            options (dict, optional): Additional options for data retrieval.
        """
        if options is None:
            options = {}

        self.print("SPACE_IGNITE_START", symbol=self.symbol)

        raw_polars = get_data(
            symbol=self.symbol,
            timeframe=self.timeframe,
            after_ms=self.after_ms,
            until_ms=self.until_ms,
            limit=self.limit,
            order="asc",
            indicators=self.features_to_request,
            options={**options, "return_polars": True}
        )

        df = raw_polars.to_pandas()
        max_time_date = pd.to_datetime(df['time_ms'].max(), unit='ms').strftime('%Y-%m-%d')
        self.print("SPACE_BOUNDARY", date=max_time_date)

        # Handle Target Column
        if self.target_col in df.columns:
            raw_target = df[self.target_col].copy()
            if not pd.api.types.is_numeric_dtype(raw_target):
                raw_target = pd.to_numeric(raw_target, errors='coerce').fillna(0)

            pos_count = (raw_target == 1).sum()
            neg_count = (raw_target == -1).sum()
            
            self.print("DATA_AUDIT_TARGET", target=self.target_col)
            self.print("DATA_AUDIT_BARS", count=len(df))
            self.print("DATA_AUDIT_SIGS", sigs=pos_count + neg_count)

            self._target_series = (raw_target != 0).astype(np.float32)
            self._target_series.name = "target"
        else:
            self.print("SPACE_ERROR_TARGET", target=self.target_col)
            self._target_series = pd.Series(np.zeros(len(df)), name="target")

        # Filter Patterns & Metadata
        cols_to_drop = []
        for pattern in self.filter_patterns:
            cols_to_drop.extend(fnmatch.filter(df.columns, pattern))

        metadata = ['time_ms', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'timeframe']
        final_drops = list(set(cols_to_drop + [c for c in metadata if c in df.columns]))
        if self.target_col in df.columns and self.target_col not in final_drops:
            final_drops.append(self.target_col)

        work_df = df.drop(columns=[c for c in final_drops if c in df.columns])
        work_df = work_df.bfill().ffill().fillna(0)

        numeric_df = work_df.select_dtypes(include=[np.number])
        self._discarded_dimensions = [c for c in work_df.columns if c not in numeric_df.columns]

        self._feature_table = numeric_df
        self._feature_names = self._feature_table.columns.tolist()

        if self._discarded_dimensions:
            self.print("SPACE_CLEANUP_STRINGS", count=len(self._discarded_dimensions))
        
        self.print("SPACE_DISCOVERY", count=len(self._feature_names))
