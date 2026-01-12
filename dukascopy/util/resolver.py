#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resolver.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Description: Provides functionality to resolve user dataset selection
              strings into actionable tasks for the Dukascopy data pipeline.

              The `SelectionResolver` class manages a set of available datasets
              and supports parsing selection strings in the form
              `SYMBOL/TF[:modifier]`, including:
                - Regex-based symbol matching with wildcards (*)
                - Comma-separated timeframes
                - Global and local modifiers

              It validates requested selections against available datasets
              and returns structured task information, including dataset paths
              and associated modifiers.

 Requirements:
     - Python 3.8+
     - etl.util.dataclass.Dataset

 License:
     MIT License
===============================================================================
"""
import os
import re
from typing import List, Tuple, Set, Dict

from util.dataclass import Dataset

class SelectionResolver:
    def __init__(self, available_data: List[Dataset]):
        """Initializes the container with available datasets.

        Args:
            available_data (List[Dataset]): A list of dataset objects produced by
                the main data pipeline. Each dataset is expected to expose at
                least `key` and `symbol` attributes.

        Raises:
            Exception: If no datasets are provided, indicating the pipeline
                has not been run or produced no results.
        """
        # Validate that datasets are provided
        if not available_data:
            raise Exception("No datasets found. Run the main pipeline first.")
            
        # Store the full list of available datasets
        self.available = available_data

        # Build a set of all available dataset symbols for fast membership checks
        self.available_symbols = {d.symbol for d in available_data}

        # Create a lookup map from dataset key to dataset instance
        self.dataset_map = {d.key: d for d in available_data}


    def resolve(self, select_args: List[str], force: bool = False):
        """Resolves user selection strings into executable dataset tasks.

        This method parses selection arguments of the form
        `SYMBOL/TF[:modifier]`, supporting regex-based symbol matching,
        comma-separated timeframes, and both global and local modifiers.
        It validates requested datasets against those available and
        returns a structured list of tasks ready for execution.

        Args:
            select_args (List[str]): A list of selection strings specifying
                symbols, timeframes, and optional modifiers.
            force (bool): Whether to bypass validation errors for unresolved
                symbol/timeframe pairs.

        Returns:
            Tuple[List[Tuple[str, str, str, List[str]]], Set[Tuple[str, str]]]:
                A sorted list of resolved tasks in the form
                (symbol, timeframe, path, modifiers), and a set of resolved
                (symbol, timeframe) pairs.

        Raises:
            Exception: If validation fails and `force` is False.
        """
        # Map of (symbol, timeframe) to the best dataset and its modifiers
        best_tasks: Dict[Tuple[str, str], Tuple[Dataset, List[str]]] = {}

        # Track all requested (symbol, timeframe) pairs for validation
        requested_pairs: Set[Tuple[str, str]] = set()

        # Process each user-provided selection argument
        for selection in select_args:
            # Split the selection into raw symbol and timeframe components
            symbol_raw, tf_raw = self._split_selection(selection)
            
            # Parse symbol pattern and any global modifiers
            symbol_pattern, global_mods = self._parse_mods(symbol_raw)

            # Expand comma-separated timeframe specifications
            tf_specs = [t.strip() for t in tf_raw.split(",")]

            # Resolve symbol pattern to matching symbols (regex-supported)
            matched_symbols = self._match_symbols(symbol_pattern)

            # Iterate over all resolved symbols and timeframe specs
            for symbol in (matched_symbols or [symbol_pattern]):
                for tf_spec in tf_specs:
                    # Parse timeframe base and local modifiers
                    tf_base, local_mods = self._parse_mods(tf_spec)

                    # Identify the symbol/timeframe pair
                    pair = (symbol, tf_base)
                    requested_pairs.add(pair)

                    # Skip pairs that do not exist in the dataset map
                    if pair not in self.dataset_map:
                        continue

                    # Merge global and local modifiers, preserving order
                    combined_mods = list(dict.fromkeys(global_mods + local_mods))
                    
                    # Select the dataset associated with this pair
                    dataset = self.dataset_map[pair]

                    # Record or overwrite the best task for this pair
                    best_tasks[pair] = (dataset, combined_mods)

        # Determine which requested pairs were successfully resolved
        resolved_pairs = set(best_tasks.keys())

        # Validate results unless forced
        self._validate_results(requested_pairs, resolved_pairs, force)

        # Return sorted, structured tasks and resolved pairs
        return sorted([
            (d.symbol, d.timeframe, d.path, mods)
            for d, mods in best_tasks.values()
        ]), resolved_pairs


    def _split_selection(self, selection: str) -> Tuple[str, str]:
        """Splits a selection string into symbol and timeframe components.

        The expected input format is `SYMBOL/TF`. If the delimiter is missing,
        an exception is raised to signal an invalid selection.

        Args:
            selection (str): A selection string in the form `SYMBOL/TF`.

        Returns:
            Tuple[str, str]: A tuple containing the symbol portion and the
                timeframe portion of the selection string.

        Raises:
            Exception: If the selection string does not contain a `/` separator.
        """
        # Ensure the selection string follows the expected SYMBOL/TF format
        if "/" not in selection:
            raise Exception(f"Invalid format: {selection} (expected SYMBOL/TF)")

        # Split on the first '/' only, allowing '/' in later components if needed
        return selection.split("/", 1)


    def _parse_mods(self, part: str) -> Tuple[str, List[str]]:
        """Parses a string into a base value and optional modifiers.

        The input is expected to use colon (`:`) separators, where the first
        segment represents the base value and any subsequent segments are
        treated as modifiers.

        Args:
            part (str): A string containing a base value optionally followed
                by one or more colon-separated modifiers.

        Returns:
            Tuple[str, List[str]]: A tuple consisting of the base value and
                a list of modifier strings (empty if none are present).
        """
        # Split the string on colon separators
        bits = part.split(":")

        # The first element is the base value; the rest are modifiers
        return bits[0], bits[1:]


    def _match_symbols(self, pattern: str) -> List[str]:
        """Matches available symbols against a pattern.

        Supports exact symbol matching as well as simple wildcard patterns
        using `*`, which are internally converted to regular expressions.

        Args:
            pattern (str): A symbol name or wildcard pattern to match against
                the available symbols.

        Returns:
            List[str]: A list of symbols that match the given pattern.
        """
        # Check for wildcard usage in the pattern
        if "*" in pattern:
            # Convert simple wildcard syntax to a regular expression
            regex = pattern.replace(".", r"\.").replace("*", ".*")

            # Return all symbols that fully match the generated regex
            return [s for s in self.available_symbols if re.fullmatch(regex, s)]

        # Fallback to exact symbol matching
        return [s for s in self.available_symbols if s == pattern]


    def _validate_results(self, requested, resolved, force):
        """Validates that all requested symbol/timeframe pairs were resolved.

        Compares the set of requested pairs against the set of successfully
        resolved pairs and raises an error if any remain unresolved, unless
        validation is explicitly forced.

        Args:
            requested (Set[Tuple[str, str]]): All symbol/timeframe pairs
                requested by the user.
            resolved (Set[Tuple[str, str]]): The subset of requested pairs
                that were successfully resolved.
            force (bool): If True, unresolved pairs are ignored and no
                exception is raised.

        Raises:
            Exception: If unresolved pairs exist and `force` is False.
        """
        # Determine which requested pairs were not resolved
        unresolved = sorted(requested - resolved)

        # Raise an error for unresolved selections unless forced
        if unresolved and not force:
            # Format unresolved pairs for a readable error message
            err_list = "".join([f"- {s}/{tf}\n" for s, tf in unresolved])
            raise Exception(f"\nCritical Error: Unresolved selections:\n{err_list}")
