#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        discovery.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Description: Provides functionality to discover and manage datasets
              for the Dukascopy data pipeline.

              The `DataDiscovery` class scans configured directories for
              dataset files in either binary or CSV format. It supports:
                - Aggregate and resampled directory structures
                - Automatic file extension selection based on configuration
                - Construction of Dataset objects with symbol, timeframe,
                  and file path
                - Sorting datasets by symbol and timeframe

              The discovered datasets are stored internally and returned
              as a sorted list for further processing by downstream
              ETL tasks.

 Requirements:
     - Python 3.8+
     - etl.util.dataclass.Dataset

 License:
     MIT License
===============================================================================
"""
import os
import re
from typing import List, Set, Dict

from etl.util.dataclass import Dataset

class DataDiscovery:
    def __init__(self, config: 'BuilderConfig'): # TODO: change builderconfig
        """Initializes the builder with configuration and sets up datasets.

        This constructor stores the provided configuration, determines the file
        extension based on the mode (binary or CSV), and initializes an empty
        list to hold dataset objects.

        Args:
            config (BuilderConfig): Configuration object containing settings
                for the builder, including file mode and other parameters.
        """
        # Store the builder configuration
        self.config = config

        # Determine file extension based on configuration mode
        self.extension = ".bin" if config.fmode == "binary" else ".csv"

        # Initialize an empty list to hold Dataset instances
        self._datasets: List[Dataset] = []


    def scan(self) -> List[Dataset]:
        """Scans the filesystem for datasets based on configuration paths.

        This method inspects both aggregate and resampled directories
        under the configured data path, identifies files matching the
        builder's file extension, and constructs Dataset objects for
        each valid file. The discovered datasets are stored internally
        and returned as a sorted list.

        Returns:
            List[Dataset]: A list of Dataset instances found in the
                filesystem, sorted by symbol and timeframe.
        """
        # Get the base data directory from the configuration
        data_dir = self.config.paths.data
        if not os.path.isdir(data_dir):
            return []

        # Initialize mapping from timeframe to directory path
        scan_map: Dict[str, str] = {
            "1m": os.path.join(data_dir, "aggregate", "1m")
        }

        # Include all resampled directories if they exist
        resample_dir = os.path.join(data_dir, "resample")
        if os.path.isdir(resample_dir):
            with os.scandir(resample_dir) as it:
                for entry in it:
                    if entry.is_dir():
                        scan_map[entry.name] = entry.path

        # Set to hold unique Dataset objects
        found: Set[Dataset] = set()
        ext_len = len(self.extension)

        # Iterate over each timeframe and its corresponding directory
        for tf, dir_path in scan_map.items():
            if not os.path.isdir(dir_path):
                continue
            
            abs_dir = os.path.abspath(dir_path)
            with os.scandir(dir_path) as it:
                for entry in it:
                    # Include only files with the configured extension
                    if entry.is_file() and entry.name.endswith(self.extension):
                        # Derive the symbol name from the filename
                        symbol = entry.name[:-ext_len]
                        # Create Dataset object and add to the set
                        found.add(Dataset(
                            symbol=symbol, 
                            timeframe=tf, 
                            path=os.path.join(abs_dir, entry.name)
                        ))

        # Sort datasets by symbol and timeframe and store internally
        self._datasets = sorted(list(found), key=lambda d: (d.symbol, d.timeframe))
        return self._datasets
