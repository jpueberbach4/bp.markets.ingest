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
import re
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


def get_available_data_from_fs(
    config: BuilderConfig,
) -> List[Tuple[str, str, str]]:
    """
    Scan the filesystem for available CSV datasets based on the
    BuilderConfig paths.

    Parameters:
    -----------
    config : BuilderConfig
        Application configuration containing data paths.

    Returns:
    --------
    List[Tuple[str, str, str]]
        Sorted list of tuples containing (symbol, timeframe, file_path).
    """
    data_dir = Path(config.paths.data)
    if not data_dir.is_dir():
        return []

    # Base scan directories
    scan_dirs: Dict[str, Path] = {"1m": data_dir / "aggregate" / "1m"}

    # Add resampled timeframes
    resample_dir = data_dir / "resample"
    if resample_dir.is_dir():
        for tf_dir in resample_dir.iterdir():
            if tf_dir.is_dir():
                scan_dirs[tf_dir.name] = tf_dir

    available_data: Set[Tuple[str, str, str]] = set()

    # Iterate through directories and collect CSV files
    for timeframe, dir_path in scan_dirs.items():
        if not dir_path.is_dir():
            continue
        for csv_file in dir_path.glob("*.csv"):
            available_data.add(
                (csv_file.stem, timeframe, str(csv_file.resolve()))
            )

    return sorted(available_data)


def resolve_selections(
    select_args: List[str],
    all_available_data: List[Tuple[str, str, str]],
    force: bool,
) -> Tuple[
    List[Tuple[str, str, str, Optional[str]]],
    Set[Tuple[str, str]],
]:
    """
    Resolve user selection strings into concrete dataset tasks.

    Parameters:
    -----------
    parser : CustomArgumentParser
        Parser used to report errors and print help.
    select_args : List[str]
        List of selection strings in the format SYMBOL/TF[:modifier].
    all_available_data : List[Tuple[str, str, str]]
        List of available datasets (symbol, timeframe, file_path).
    force : bool
        If True, unresolved selections will not raise errors.

    Returns:
    --------
    Tuple[
        List[Tuple[str, str, str, Optional[str]]],
        Set[Tuple[str, str]]
    ]
        - Sorted list of resolved dataset tasks with optional modifiers.
        - Set of resolved (symbol, timeframe) pairs.
    """
    if not all_available_data:
        raise Exception("No datasets found to select from. Run the main pipeline first.")

    # Sets of available symbols and (symbol, timeframe) pairs
    available_symbols = {s for s, _, _ in all_available_data}
    available_pairs = {(s, tf) for s, tf, _ in all_available_data}

    best_tasks: Dict[
        Tuple[str, str],
        Tuple[str, str, str, Optional[str]],
    ] = {}
    requested_pairs: Set[Tuple[str, str]] = set()

    for selection in select_args:
        if "/" not in selection:
            raise Exception(f"Invalid format: {selection} (expected SYMBOL/TF[:modifier])")
        
        symbol_part, tf_part = selection.split("/", 1)
        
        symbol_mods = []
        if ":" in symbol_part:
            parts = symbol_part.split(":")
            symbol_pattern = parts[0]
            symbol_mods = parts[1:]
        else:
            symbol_pattern = symbol_part

        tf_specs = [tf.strip() for tf in tf_part.split(",")]

        # Wildcards not yet implemented
        if "*" in symbol_pattern:
            raise NotImplementedError("Symbol wildcards are not yet implemented.")
        if any("*" in tf.split(":")[0] for tf in tf_specs):
            raise NotImplementedError("Timeframe wildcards are not yet implemented.")

        # Regex match symbols
        regex = symbol_pattern.replace(".", r"\.").replace("*", ".*")
        matched_symbols = [s for s in available_symbols if re.fullmatch(regex, s)]

        # Fallback to original pattern if no match
        for symbol in matched_symbols or [symbol_pattern]:
            for tf_spec in tf_specs:
                tf_base, *tf_mods = tf_spec.split(":")

                modifiers = list(dict.fromkeys(symbol_mods + tf_mods))

                pair = (symbol, tf_base)
                requested_pairs.add(pair)

                if pair not in available_pairs:
                    continue

                # Find source file path for this pair
                source_path = next(
                    path for s, tf, path in all_available_data if s == symbol and tf == tf_base
                )

                new_task = (symbol, tf_base, source_path, modifiers)
                current_modifier = best_tasks.get(pair, (None, None, None, None))[3]

                # Prefer tasks with a defined modifier
                if current_modifier is None or modifier is not None:
                    best_tasks[pair] = new_task

    resolved_pairs = set(best_tasks.keys())
    unresolved_pairs = sorted(requested_pairs - resolved_pairs)

    # Raise error for unresolved selections if force is False
    if unresolved_pairs and not force:
        msg = (
            "\nCritical Error: The following selections match no existing files:\n"
            + "".join(f"- {s}/{tf}\n" for s, tf in unresolved_pairs)
        )
        raise Exception(msg)

    return sorted(best_tasks.values()), resolved_pairs