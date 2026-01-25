#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        registry.py
Author:      JP Ueberbach
Created:     2026-01-12
Updated:     2026-01-23

Dataset registry management for the Dukascopy data pipeline.

This module defines the `DatasetRegistry` class, which provides fast
lookup and access to dataset objects for different financial instruments
(symbols) and their associated timeframes.

It uses a nested dictionary structure for O(1) retrieval of datasets
by symbol and timeframe. The registry also exposes methods to list
available datasets and the timeframes associated with each symbol.

Classes:
    DatasetRegistry: Maintains a registry of Dataset objects for quick lookup.

Dependencies:
    - Python 3.8+
    - dataclasses (standard library)
    - util.dataclass.Dataset

License:
    MIT License
===============================================================================
"""

from util.dataclass import Dataset
from typing import List, Optional


class DatasetRegistry:
    """Registry for fast access to Dataset objects by symbol and timeframe."""

    def __init__(self, datasets: List[Dataset]):
        """Initialize the registry with a list of Dataset objects.

        Args:
            datasets (List[Dataset]): List of Dataset instances to register.
        """
        # Internal nested lookup dictionary {symbol: {timeframe: Dataset}}
        self._lookup = {}

        # Store all datasets as a flat list
        self._datasets = datasets

        # Build the nested lookup dictionary
        self._index_datasets(datasets)

    def _index_datasets(self, datasets: List[Dataset]):
        """Populate the internal nested dictionary for fast symbol/timeframe lookup.

        Args:
            datasets (List[Dataset]): List of Dataset instances to index.
        """
        # Iterate through all provided datasets
        for ds in datasets:
            # Initialize symbol key if it does not exist
            if ds.symbol not in self._lookup:
                self._lookup[ds.symbol] = {}

            # Map timeframe to dataset for the given symbol
            self._lookup[ds.symbol][ds.timeframe] = ds

    def find(self, symbol: str, timeframe: str) -> Optional[Dataset]:
        """Retrieve a Dataset for a given symbol and timeframe.

        Args:
            symbol (str): The financial instrument symbol (e.g., 'EURUSD').
            timeframe (str): The timeframe identifier (e.g., '1m', '1h').

        Returns:
            Optional[Dataset]: The corresponding Dataset object if found,
                               otherwise None.
        """
        # Use nested dictionary lookup with default empty dict
        return self._lookup.get(symbol, {}).get(timeframe)

    def get_available_datasets(self) -> List[Dataset]:
        """Return the list of all registered Dataset objects.

        Returns:
            List[Dataset]: Flat list of all Dataset instances in the registry.
        """
        return self._datasets

    def get_available_timeframes(self, symbol: str) -> List[str]:
        """Return all timeframes available for a given symbol.

        Args:
            symbol (str): The symbol for which to list timeframes.

        Returns:
            List[str]: List of timeframe strings associated with the symbol.
        """
        # Retrieve keys of the inner dictionary corresponding to the symbol
        return list(self._lookup.get(symbol, {}).keys())
