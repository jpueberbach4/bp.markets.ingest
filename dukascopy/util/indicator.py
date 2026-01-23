#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        indicator.py
Author:      JP Ueberbach
Created:     2026-01-23
Updated:     2026-01-23

Indicator plugin management for the Dukascopy data pipeline.

This module defines the `IndicatorRegistry` class, which is responsible for
discovering, loading, hot-reloading, and managing indicator plugins. It also
provides utility methods to inspect plugin metadata and determine warmup
requirements for indicator calculations.

Key responsibilities:
    - Discover indicator plugins from core and user directories.
    - Dynamically import and reload plugin modules from file paths.
    - Track file metadata to detect changes and support hot-reloading.
    - Expose indicator calculation functions for downstream use.
    - Build a normalized, metadata-rich registry of all loaded indicators.
    - Determine the maximum warmup row requirement across multiple indicators.

Indicator plugin interface:
    - Must define a `calculate` function for computing indicator values.
    - May optionally define:
        - `position_args(params: list) -> dict`: Map positional args to named options.
        - `warmup_count(options: dict) -> int`: Return required warmup rows.
        - `description() -> str`: Provide a human-readable description.
        - `meta() -> dict`: Return optional metadata dictionary.

Requirements:
    - Python 3.8+
    - Indicator plugins following the Dukascopy indicator interface.

License:
    MIT License
===============================================================================
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import List

class IndicatorRegistry:
    """
    Manages the lifecycle of indicator plugins, including discovery, 
    dynamic loading, hot-reloading, and metadata extraction.
    """

    def __init__(self, core_dir=None, user_dir=None):
        """Initialize the indicator plugin manager.

        This constructor configures the search paths for core and user-defined
        indicator plugins, initializes the internal plugin registry, and
        performs an initial discovery and load of all available plugins.

        Args:
            core_dir (pathlib.Path | None): Optional path to the directory
                containing built-in indicator plugins. If not provided, the
                default core indicator plugin directory relative to this file
                is used.
            user_dir (pathlib.Path | None): Optional path to the directory
                containing user-defined indicator plugins. If not provided, the
                default user plugin directory is used.
        """
        # Default paths if not provided
        self.core_dir = core_dir or (Path(__file__).parent / "plugins/indicators")
        self.user_dir = user_dir or Path("config.user/plugins/indicators")
        
        # Internal registry to store loaded plugin functions and file stats
        self.registry = {}
        
        # Initial load of all available plugins
        self.load_all_plugins()

    def _import_plugin(self, name, path):
        """Dynamically import a Python module from a filesystem path.

        This method ensures a clean import by removing any previously loaded
        module with the same name from ``sys.modules`` before loading the
        module from the provided file path. It uses Python's importlib
        utilities to construct and execute the module specification.

        Args:
            name (str): Fully qualified module name to assign to the imported plugin.
            path (str | pathlib.Path): Filesystem path to the plugin source file.

        Returns:
            module: The imported Python module instance.
        """
        # Remove existing module entry to force a clean reload
        if name in sys.modules:
            del sys.modules[name]

        # Create a module specification from the given file path
        spec = importlib.util.spec_from_file_location(name, path)

        # Instantiate a new module object from the specification
        module = importlib.util.module_from_spec(spec)

        # Execute the module in its own namespace
        spec.loader.exec_module(module)

        return module

    def load_all_plugins(self):
        """Discover and load all indicator plugins from configured directories.

        This method scans both the core and user plugin directories for Python
        files representing indicator plugins. Each valid plugin module is
        registered into the internal registry using the plugin filename as
        its identifier.

        Plugin files must:
            - Have a `.py` extension
            - Not start with `__`

        Returns:
            dict: The internal plugin registry containing all loaded plugins.
        """
        # Directories to search for indicator plugins
        search_dirs = [self.core_dir, self.user_dir]

        # Iterate over all configured plugin directories
        for plugin_dir in search_dirs:
            # Skip directories that do not exist
            if not plugin_dir.exists():
                continue

            # Iterate over Python files in the plugin directory
            for file in os.listdir(plugin_dir):
                # Ignore non-plugin files and dunder modules
                if file.endswith(".py") and not file.startswith("__"):
                    # Derive the plugin name from the filename
                    plugin_name = file[:-3]

                    # Construct the full filesystem path to the plugin
                    file_path = plugin_dir / file

                    # Register the plugin module
                    self._register_plugin(plugin_name, file_path)

        # Return the populated plugin registry
        return self.registry

    def _register_plugin(self, name, path):
        """Import and register a single indicator plugin in the internal registry.

        This method loads a Python module from the given file path, checks
        for a `calculate` callable, and stores it in the internal plugin
        registry along with file metadata for potential future hot reloads.

        Args:
            name (str): The identifier to register the plugin under.
            path (Path): Filesystem path to the plugin Python file.

        Returns:
            None
        """
        # Get file metadata for potential hot-reload checks
        file_stat = path.stat()

        # Dynamically import the plugin module
        module = self._import_plugin(name, path)

        # Only register modules that implement the `calculate` function
        if hasattr(module, "calculate"):
            self.registry[name] = {
                'calculate': module.calculate,   # Reference to plugin function
                'mtime': file_stat.st_mtime,     # Last modification timestamp
                'size': file_stat.st_size        # File size for change detection
            }

    def refresh(self, indicators: List[str] = []):
        """Reload or refresh indicator plugins from disk based on specified names.

        This method ensures that the plugin registry is up to date. It will
        either reload all plugins if no specific indicators are provided, or
        selectively reload only those indicators whose files have changed
        on disk (modification time or size differs from cached metadata).

        Args:
            indicators (List[str], optional): List of plugin names or
                indicator selection strings (e.g., "RSI_14"). Only the
                base plugin name (before any underscore) is used for refresh.
                If empty or not provided, all plugins are reloaded.

        Returns:
            dict: The updated plugin registry mapping plugin names to their
                callable and file metadata.
        """
        # Full reload if no specific indicators provided
        if not indicators or len(indicators) == 0:
            return self.load_all_plugins()

        # Extract unique base plugin names from indicator strings
        unique_required = {item.split('_')[0] for item in indicators}

        for name in unique_required:
            # Prefer user plugin directory for overrides
            file_path = self.user_dir / f"{name}.py"
            if not file_path.exists():
                file_path = self.core_dir / f"{name}.py"

            # Skip if no plugin file exists
            if not file_path.exists():
                continue

            # Get file metadata for comparison
            file_stat = file_path.stat()
            cached = self.registry.get(name)

            # Determine if reload is necessary (new or changed file)
            needs_reload = (
                not cached or
                cached.get('mtime') != file_stat.st_mtime or
                cached.get('size') != file_stat.st_size
            )

            # Register or reload plugin if required
            if needs_reload:
                self._register_plugin(name, file_path)

        return self.registry

    def get_metadata_registry(self):
        """Build a metadata-rich dictionary of all registered indicator plugins.

        This method collects information about each loaded plugin, including
        its name, description, warmup requirements, default parameters, and
        optional metadata. It ensures that any changes on disk are reflected
        by refreshing plugins before extracting metadata.

        Returns:
            dict: A dictionary mapping plugin names to metadata dictionaries
                with the following structure:
                    - name (str): Plugin name.
                    - description (str): Human-readable description.
                    - warmup (int): Number of rows required for indicator warmup.
                    - defaults (dict): Default parameter values.
                    - meta (dict): Optional additional metadata.
        """
        # Ensure user plugins are refreshed before building metadata
        self.refresh({'select_data': []})  # Trigger full or fallback refresh

        metadata_map = {}

        # Iterate over all registered plugins
        for name, plugin_data in self.registry.items():
            func = plugin_data.get('calculate')
            globals_dict = getattr(func, "__globals__", {})

            # Initialize standardized metadata structure
            info = {
                "name": name,
                "description": "N/A",
                "warmup": 0,
                "defaults": {},
                "meta": {},
            }

            # Extract default parameters from plugin if defined
            if "position_args" in globals_dict:
                info["defaults"].update(globals_dict["position_args"]([]))

            # Determine warmup row requirement if defined
            if "warmup_count" in globals_dict:
                info["warmup"] = globals_dict["warmup_count"](info["defaults"])

            # Extract human-readable description if defined
            if "description" in globals_dict:
                info["description"] = globals_dict["description"]()

            # Extract additional plugin metadata if defined
            if "meta" in globals_dict:
                info["meta"].update(globals_dict["meta"]())

            # Add to metadata map
            metadata_map[name] = info

        # Return metadata sorted alphabetically by plugin name
        return {k: metadata_map[k] for k in sorted(metadata_map)}


    def get_maximum_warmup_rows(self, indicators: List[str]) -> int:
        """Determine the maximum warmup row count required by a set of indicators.

        This function inspects each requested indicator plugin to determine how many
        historical rows are required before the `after_str` timestamp in order to
        correctly compute indicator values (e.g., rolling windows). The maximum
        warmup requirement across all indicators is returned.

        Args:
            symbol (str): Trading symbol (e.g., "EURUSD"). Included for interface
                consistency and future extensibility.
            timeframe (str): Timeframe identifier (e.g., "5m", "1h"). Included for
                interface consistency and future extensibility.
            after_str (str): ISO-formatted timestamp string representing the starting
                point of the query. Not modified by this function.
            indicators (List[str]): List of indicator strings (e.g., ["sma_20", "bbands_20_2"]).

        Returns:
            int: The maximum number of warmup rows required across all indicators.
        """
        # Track the largest warmup requirement found
        max_rows = 0

        # Iterate through all requested indicators
        for ind_str in indicators:
            parts = ind_str.split('_')
            name = parts[0]

            # Skip indicators that are not registered
            if name not in self.registry:
                continue

            plugin_func = self.registry[name].get('calculate')

            # Initialize indicator options with raw positional parameters
            ind_opts = {"params": parts[1:]}

            # Map positional arguments if the plugin defines a mapper
            if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
                ind_opts.update(plugin_func.__globals__["position_args"](parts[1:]))

            # Query the plugin for its warmup row requirement, if defined
            if hasattr(plugin_func, "__globals__") and "warmup_count" in plugin_func.__globals__:
                warmup_rows = plugin_func.__globals__["warmup_count"](ind_opts)
                max_rows = max(max_rows, warmup_rows)

        return max_rows