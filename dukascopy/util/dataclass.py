#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        dataclass.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Description: Defines the Dataset dataclass used across the Dukascopy
              data pipeline.

              The `Dataset` class represents a single dataset file and 
              stores:
                - `symbol`: The financial instrument symbol
                - `timeframe`: The data timeframe (e.g., 1m, 1h)
                - `path`: The full filesystem path to the dataset file

              It also provides a `key` property that returns a tuple
              `(symbol, timeframe)` for convenient indexing and mapping
              in resolver or discovery modules.

 Requirements:
     - Python 3.8+
     - dataclasses (standard library)

 License:
     MIT License
===============================================================================
"""

from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Dataset:
    symbol: str
    timeframe: str
    path: str

    @property
    def key(self) -> Tuple[str, str]:
        return (self.symbol, self.timeframe)