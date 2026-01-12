#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        helper.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Module providing utility functions for managing Dukascopy dataset 
              selections and command-line argument parsing.

              Includes:
              - CustomArgumentParser: argparse wrapper that prints help on error.
              - get_available_data_from_fs: discovers CSV datasets in the filesystem.
              - resolve_selections: parses user selection strings and matches them
                against available datasets, supporting optional modifiers.

 Requirements:
     - Python 3.8+

 License:
     MIT License
===============================================================================
"""
import argparse
import random
import sys
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set

from builder.config.app_config import BuilderConfig


class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser that prints the help message on error.
    """
    def error(self, message: str):
        sys.stderr.write(f"{message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)


def print_available_datasets(datasets: list):
    grouped = defaultdict(list)
    for ds in datasets:
        grouped[ds.symbol].append(ds.timeframe)

    tf_order = {'m': 1, 'h': 60, 'd': 1440, 'W': 10080, 'M': 43200, 'Y': 525600}
    
    def tf_sort_key(tf):
        import re
        match = re.match(r"(\d+)([a-zA-Z]+)", tf)
        if match:
            val, unit = match.groups()
            return int(val) * tf_order.get(unit, 1)
        return 0

    print("\n--- Available Symbols and Timeframes" + "-" * 44)
    for symbol in sorted(grouped.keys()):
        timeframes = sorted(grouped[symbol], key=tf_sort_key)
        formatted_tfs = ", ".join(timeframes)
        print(f"{symbol:<36} [{formatted_tfs}]")
    
    print("-" * 80)
