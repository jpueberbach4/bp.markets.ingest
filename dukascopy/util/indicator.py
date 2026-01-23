#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        indicator.py
 Author:      JP Ueberbach
 Created:     2026-01-23
 Description: Provides discovery, loading, and management of indicator plugins
              for the Dukascopy data pipeline.

              This module defines the `IndicatorManager` class, which is
              responsible for:
                - Discovering indicator plugins from core and user directories
                - Dynamically importing and hot-reloading indicator modules
                - Tracking plugin file metadata to detect changes
                - Exposing registered indicator calculation functions
                - Building a normalized metadata registry for all indicators
                - Determining warmup row requirements across multiple indicators

              Indicator plugins are expected to expose a `calculate` function
              and may optionally define supporting metadata functions such as
              `position_args`, `warmup_count`, `description`, and `meta`.

 Requirements:
     - Python 3.8+
     - Indicator plugins following the Dukascopy indicator interface

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
        # Default paths if not provided
        self.core_dir = core_dir or (Path(__file__).parent / "plugins/indicators")
        self.user_dir = user_dir or Path("config.user/plugins/indicators")
        
        # Internal registry to store loaded plugin functions and file stats
        self.registry = {}
        
        # Initial load of all available plugins
        self.load_all_plugins()

    def _import_plugin(self, name, path):
        """Helper to dynamically import a module from a file path."""
        # Ensure a clean reload by removing from sys.modules if it exists
        if name in sys.modules:
            del sys.modules[name]
            
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_all_plugins(self):
        """Dynamically discover and load all indicator plugins from search dirs."""
        search_dirs = [self.core_dir, self.user_dir]
        
        for plugin_dir in search_dirs:
            if not plugin_dir.exists():
                continue

            for file in os.listdir(plugin_dir):
                if file.endswith(".py") and not file.startswith("__"):
                    plugin_name = file[:-3]
                    file_path = plugin_dir / file
                    self._register_plugin(plugin_name, file_path)
        
        return self.registry

    def _register_plugin(self, name, path):
        """Imports and adds a specific plugin to the registry if valid."""
        file_stat = path.stat()
        module = self._import_plugin(name, path)

        if hasattr(module, "calculate"):
            self.registry[name] = {
                'calculate': module.calculate,
                'mtime': file_stat.st_mtime,
                'size': file_stat.st_size
            }

    def refresh(self, indicators: List[str] = []):
        """
        Refreshes plugins based on 'options' selection or reloads 
        user plugins if files have changed on disk.
        """
        # If no options, do a full reload of everything
        if not indicators or not len(indicators) == 0:
            return self.load_all_plugins()

        # Extract unique plugin names from select_data strings (e.g., "RSI_14" -> "RSI")
        unique_required = {
            item.split('_')[0] 
            for item in indicators
        }

        for name in unique_required:
            # We check the user directory first for overrides
            file_path = self.user_dir / f"{name}.py"
            if not file_path.exists():
                file_path = self.core_dir / f"{name}.py"

            if not file_path.exists():
                continue

            # Check if reload is necessary
            file_stat = file_path.stat()
            cached = self.registry.get(name)

            needs_reload = (
                not cached or
                cached.get('mtime') != file_stat.st_mtime or
                cached.get('size') != file_stat.st_size
            )

            if needs_reload:
                self._register_plugin(name, file_path)

        return self.registry

    def get_metadata_registry(self):
        """
        Builds a normalized, metadata-rich dictionary of all registered indicators.
        """
        # Refresh user indicators specifically before building metadata
        self.refresh({'select_data': []}) # Trigger fallback or targeted refresh

        metadata_map = {}

        for name, plugin_data in self.registry.items():
            func = plugin_data.get('calculate')
            globals_dict = getattr(func, "__globals__", {})

            # Standardized structure
            info = {
                "name": name,
                "description": "N/A",
                "warmup": 0,
                "defaults": {},
                "meta": {},
            }

            # Extract info from plugin-defined global callables
            if "position_args" in globals_dict:
                info["defaults"].update(globals_dict["position_args"]([]))
            
            if "warmup_count" in globals_dict:
                info["warmup"] = globals_dict["warmup_count"](info["defaults"])
            
            if "description" in globals_dict:
                info["description"] = globals_dict["description"]()
            
            if "meta" in globals_dict:
                info["meta"].update(globals_dict["meta"]())

            metadata_map[name] = info

        # Return sorted by key
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