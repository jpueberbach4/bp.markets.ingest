#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        plugin.py
 Author:      JP Ueberbach
 Created:     2026-01-07
 Description: Plugin loading and management for indicator modules.

 This module provides dynamic discovery, loading, caching, and hot-reloading
 of indicator plugins. Indicator plugins are Python modules that expose a
 ``calculate`` function and may optionally define metadata helpers such as
 ``position_args``, ``warmup_count``, ``description``, and ``meta``.

 The module supports both core (built-in) indicator plugins and user-defined
 plugins, tracks file metadata to enable efficient reloads when plugin source
 files change, and normalizes plugin metadata into a consistent registry
 format for downstream consumption.

 Typical usage:
    - Load all available indicator plugins at startup.
    - Refresh only selected indicators when configuration changes.
    - Extract normalized indicator metadata for UI or execution planning.

 Requirements:
    - Python 3.8+
    - FastAPI (indirect usage)
    - DuckDB (indirect usage)

 Attributes:
    indicator_registry (dict): Global registry of loaded indicator plugins,
        keyed by plugin name and containing callable and file metadata.
 License:
    MIT License
===============================================================================
"""

import os
import importlib.util
from pathlib import Path

indicator_stats = {}

def load_indicator_plugins():
    """Dynamically discover and load indicator plugins.

    This function searches predefined plugin directories for Python files,
    dynamically imports each valid plugin module, and registers its
    ``calculate`` function along with basic file metadata. Plugins are keyed
    by their filename (without the ``.py`` extension).

    Both core (built-in) and user-specific plugin directories are scanned.
    If a plugin exposes a ``calculate`` attribute, it is added to the
    returned registry.

    Returns:
        dict[str, dict]: A dictionary mapping plugin names to plugin metadata.
        Each value contains:
            - 'calculate': The plugin's calculate callable
            - 'mtime': Last modification time of the plugin file
            - 'size': File size of the plugin file
        If no plugins are found, an empty dictionary is returned.
    """
    # Registry of loaded plugins and their metadata
    plugins = {}

    # Core (bundled) plugin directory
    core_dir = Path(__file__).parent.parent / "plugins/indicators"
    # User-specific plugin directory
    user_dir = Path("config.user/plugins/indicators")

    # Directories to search for plugins
    search_dirs = [core_dir, user_dir]

    # Iterate through each plugin directory
    for plugin_dir in search_dirs:
        # Skip directories that do not exist
        if not plugin_dir.exists():
            continue

        # Iterate over files in the plugin directory
        for file in os.listdir(plugin_dir):
            # Only consider valid Python plugin files
            if file.endswith(".py") and not file.startswith("__"):
                # Derive plugin name from filename
                plugin_name = file[:-3]
                file_path = plugin_dir / file

                # Capture file metadata for hot-reload tracking
                file_stat = file_path.stat()
                current_mtime = file_stat.st_mtime
                current_size = file_stat.st_size

                # Dynamically import the plugin module
                spec = importlib.util.spec_from_file_location(plugin_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Register the plugin if it exposes a calculate function
                if hasattr(module, "calculate"):
                    plugins[plugin_name] = {
                        'calculate': module.calculate,
                        'mtime': current_mtime,
                        'size': current_size
                    }

    # Return the populated plugin registry
    return plugins


def refresh_indicators(options, indicator_registry, plugin_dir_path):
    """Refresh and reload indicator plugins when their source files change.

    This function inspects the selected indicators in ``options`` to determine
    which indicator plugins are required. For each required plugin, it checks
    whether the corresponding Python file has changed (based on file
    modification time and size). If a change is detected or the plugin is not
    yet cached, the plugin module is reloaded and its ``calculate`` function
    is stored in the registry.

    If no options or no selected data are provided, all indicator plugins
    are loaded via ``load_indicator_plugins``.

    Args:
        options (dict): Configuration dictionary that may contain a
            ``'select_data'`` key. Each item in ``select_data`` is expected
            to include a list of indicator strings at index 4.
        indicator_registry (dict): Cache of loaded indicator plugins.
            Keys are plugin names, and values are dictionaries containing:
            - 'calculate': the plugin's calculate function
            - 'mtime': last modification time of the plugin file
            - 'size': file size of the plugin file
        plugin_dir_path (str or Path): Path to the directory containing
            indicator plugin Python files.

    Returns:
        dict: Updated indicator registry with newly loaded or refreshed
        plugins.
    """
    # If no options or no selected data is provided, fall back to loading
    # all indicator plugins.
    if not options or not options.get('select_data'):
        return load_indicator_plugins()

    # Extract unique plugin names from selected indicator strings.
    # Assumes indicator strings are formatted like "<plugin>_<something>".
    unique_plugins = {
        indicator_str.split('_')[0]
        for item in options['select_data']
        for indicator_str in item[4]
    }

    # Track which plugins have already been processed in this pass
    # to avoid duplicate work.
    checked_in_pass = set()

    for plugin_name in unique_plugins:
        # Skip plugins already checked during this refresh cycle.
        if plugin_name in checked_in_pass:
            continue

        # Build the expected file path for the plugin.
        file_path = Path(plugin_dir_path) / f"{plugin_name}.py"

        # Skip if the plugin file does not exist.
        if not file_path.exists():
            continue

        # Read file metadata used to detect changes.
        file_stat = file_path.stat()
        current_mtime = file_stat.st_mtime
        current_size = file_stat.st_size

        # Retrieve cached plugin info, if any.
        cached = indicator_registry.get(plugin_name)

        # Determine whether the plugin needs to be (re)loaded.
        needs_reload = (
            not cached or
            cached.get('mtime') != current_mtime or
            cached.get('size') != current_size
        )

        if needs_reload:
            # Dynamically load the plugin module from its file path.
            spec = importlib.util.spec_from_file_location(plugin_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Only register the plugin if it exposes a calculate function.
            if hasattr(module, "calculate"):
                indicator_registry[plugin_name] = {
                    'calculate': module.calculate,
                    'mtime': current_mtime,
                    'size': current_size
                }

        # Mark this plugin as checked for the current pass.
        checked_in_pass.add(plugin_name)

    # Return the updated registry.
    return indicator_registry
     

def get_indicator_plugins(plugins):
    """
    Build a normalized, metadata-rich registry of indicator plugins.

    This function inspects registered indicator plugin functions and extracts
    standardized metadata such as default parameters, warmup requirements,
    descriptions, and arbitrary plugin-defined metadata. The resulting
    dictionary is sorted by indicator name to ensure deterministic ordering.

    Args:
        plugins (dict): Mapping of indicator names to plugin objects. The names
            are used to resolve the corresponding indicator functions from the
            global indicator registry.

    Returns:
        dict: A sorted dictionary keyed by indicator name. Each value contains
        metadata describing the indicator, with the following structure:

        {
            "name": str,
            "description": str,
            "warmup": int,
            "defaults": dict,
            "meta": dict
        }

    Notes:
        Indicator plugins may optionally expose the following globals to enrich
        their metadata:

        - position_args: Callable returning a mapping of positional argument
          names to default values.
        - warmup_count: Callable returning the number of warmup rows required.
        - description: Callable returning a human-readable description.
        - meta: Callable returning arbitrary metadata.
    """
    # Container for all discovered indicator metadata
    indicators = {}

    # Support for hot-reload (custom indicators only)
    indicator_registry_local = refresh_indicators({}, indicator_registry, "config.user/plugins/indicators")

    # Iterate through provided plugins by name
    for name, plugin in plugins.items():

        # Resolve the actual indicator function from the registry
        plugin_func = indicator_registry_local[name].get('calculate')

        # Initialize metadata structure with defaults
        info = {
            "name": name,
            "description": "N/A",
            "warmup": 0,
            "defaults": {},
            "meta": {},
        }

        # Populate default parameter values from positional argument mapper
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            info["defaults"].update(
                plugin_func.__globals__["position_args"]([])
            )

        # Determine the number of warmup rows required by the indicator
        if hasattr(plugin_func, "__globals__") and "warmup_count" in plugin_func.__globals__:
            info["warmup"] = plugin_func.__globals__["warmup_count"](
                info["defaults"]
            )

        # Retrieve a human-readable description from the plugin, if available
        if hasattr(plugin_func, "__globals__") and "description" in plugin_func.__globals__:
            info["description"] = plugin_func.__globals__["description"]()

        # Retrieve arbitrary plugin-defined metadata, if available
        if hasattr(plugin_func, "__globals__") and "meta" in plugin_func.__globals__:
            info["meta"].update(plugin_func.__globals__["meta"]())

        # Store the collected metadata for this indicator
        indicators[name] = info

    # Sort indicators by name for deterministic output
    sorted_data = {k: indicators[k] for k in sorted(indicators)}
    return sorted_data

# Global variable
indicator_registry = load_indicator_plugins()