#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        resolver.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Description: Resolves user dataset selection strings into executable tasks
              for the Dukascopy data pipeline.

              The `SelectionResolver` class operates on a collection of
              available Dataset objects and parses selection strings of
              the form:

                  SYMBOL[mods][indicators]/TF[mods][indicators]

              Supported features include:
                - Regex-based symbol matching with wildcards (*)
                - Bracket-aware parsing to safely handle nested expressions
                - Global (symbol-level) and local (timeframe-level) modifiers
                - Indicator definitions enclosed in square brackets
                  (e.g., ema(20) → ema_20)
                - Comma-separated timeframe specifications
                - Validation of requested symbol/timeframe pairs

              The resolver returns structured task definitions containing
              dataset metadata, resolved modifiers, and resolved indicators,
              suitable for downstream ETL or analysis workflows.

 Requirements:
     - Python 3.8+
     - util.dataclass.Dataset

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
        `SYMBOL/TF[mods][inds]`, supporting:
        - Regex-based symbol matching with wildcards
        - Bracket-aware parsing of modifiers and indicators
        - Comma-separated timeframe specifications
        - Global (symbol-level) and local (timeframe-level) modifiers
            and indicators

        It validates requested symbol/timeframe pairs against the available
        datasets and returns structured task definitions suitable for
        downstream processing.

        Args:
            select_args (List[str]): A list of selection strings specifying
                symbols, timeframes, modifiers, and indicators.
            force (bool): Whether to bypass validation errors for unresolved
                symbol/timeframe pairs.

        Returns:
            Tuple[List[List[Any]], Set[Tuple[str, str]]]:
                A sorted list of resolved tasks in the form
                [symbol, timeframe, path, modifiers, indicators], and a set
                of resolved (symbol, timeframe) pairs.

        Raises:
            Exception: If validation fails and `force` is False.
        """
        # Map (symbol, timeframe) to dataset, modifiers, and indicators
        best_tasks: Dict[Tuple[str, str], Tuple[Dataset, List[str], List[str]]] = {}

        # Track all requested (symbol, timeframe) pairs for validation
        requested_pairs: Set[Tuple[str, str]] = set()

        # Process each user-provided selection argument
        for selection in select_args:
            # Split the selection into symbol and timeframe portions
            symbol_raw, tf_raw = self._split_selection(selection)

            # Parse global modifiers and indicators from the symbol portion
            symbol_pattern, global_mods, global_inds = self._parse_indicators(symbol_raw)

            # Split timeframe specs by commas, ignoring commas inside brackets
            tf_specs = re.split(r',(?![^\[]*\])', tf_raw)

            # Resolve symbol patterns to concrete symbols
            matched_symbols = self._match_symbols(symbol_pattern)

            # Iterate over resolved symbols and timeframe specifications
            for symbol in (matched_symbols or [symbol_pattern]):
                for tf_spec in tf_specs:
                    # Parse local modifiers and indicators from the timeframe portion
                    tf_base, local_mods, local_inds = self._parse_indicators(tf_spec.strip())

                    # Track the requested symbol/timeframe pair
                    pair = (symbol, tf_base)
                    requested_pairs.add(pair)

                    # Skip pairs not present in the dataset map
                    if pair not in self.dataset_map:
                        continue

                    # Merge global and local modifiers, preserving order and uniqueness
                    combined_mods = list(dict.fromkeys(global_mods + local_mods))

                    # Merge global and local indicators, preserving order and uniqueness
                    combined_inds = list(dict.fromkeys(global_inds + local_inds))
                    
                    # Retrieve the dataset associated with this pair
                    dataset = self.dataset_map[pair]

                    # Record or overwrite the resolved task for this pair
                    best_tasks[pair] = (dataset, combined_mods, combined_inds)

        # Determine which requested pairs were successfully resolved
        resolved_pairs = set(best_tasks.keys())

        # Validate results unless forced
        self._validate_results(requested_pairs, resolved_pairs, force)

        # Return sorted tasks and resolved symbol/timeframe pairs
        return sorted([
            [d.symbol, d.timeframe, d.path, mods, inds]
            for d, mods, inds in best_tasks.values()
        ]), resolved_pairs



    def _split_selection(self, selection: str) -> Tuple[str, str]:
        """Splits a selection string into symbol and timeframe components.

        This method performs a bracket-aware split on the first `/` character,
        ensuring that slashes contained within bracketed expressions are ignored.
        The expected input format is `SYMBOL/TF`.

        Args:
            selection (str): A selection string in the form `SYMBOL/TF`, possibly
                containing bracketed modifiers or indicators.

        Returns:
            Tuple[str, str]: A tuple containing the symbol portion and the
                timeframe portion of the selection string.

        Raises:
            Exception: If the selection string cannot be split into exactly two
                components.
        """
        # Split on the first '/' that is not inside brackets
        parts = re.split(r'/(?![^\[]*\])', selection, 1)

        # Validate that exactly two components were produced
        if len(parts) != 2:
            raise Exception(f"Invalid format: {selection} (expected SYMBOL/TF)")

        # Return symbol and timeframe portions
        return parts[0], parts[1]



    def _parse_indicators(self, part: str) -> Tuple[str, List[str], List[str]]:
        """Parses indicators, modifiers, and base value from a selection segment.

        This method extracts indicator definitions enclosed in square brackets,
        normalizes their format (e.g., `ema(20,10)` → `ema_20_10`), and removes
        them from the input string. The remaining string is then parsed to
        extract the base value and any colon-separated modifiers.

        Args:
            part (str): A selection segment that may contain a base value,
                optional modifiers separated by colons, and optional indicators
                enclosed in square brackets.

        Returns:
            Tuple[str, List[str], List[str]]: A tuple containing:
                - base (str): The base symbol or timeframe.
                - modifiers (List[str]): A list of parsed modifier strings.
                - indicators (List[str]): A list of normalized indicator names.
        """
        # Initialize the indicator collection
        indicators = []
            
        # Search for indicator definitions enclosed in square brackets
        bracket_match = re.search(r'\[(.*?)\]', part)
        if bracket_match:
            # Extract the raw indicator content inside the brackets
            raw_inds_content = bracket_match.group(1)

            # Split indicators by ':' or '|' separators
            raw_inds_list = re.split(r'[:|]', raw_inds_content)
                
            # Normalize and collect each indicator
            for ind in raw_inds_list:
                clean = ind.strip().replace('(', '_').replace(')', '').replace(',', '_').replace('/', '_')
                if clean:
                    indicators.append(clean)

                
            # Remove the bracketed indicator portion from the input string
            part = re.sub(r'\[.*?\]', '', part)

        # Split the remaining string into base and colon-separated modifiers
        bits = part.split(":")
        base = bits[0]
        modifiers = [m for m in bits[1:] if m]

        # Return the parsed components
        return base, modifiers, indicators



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
