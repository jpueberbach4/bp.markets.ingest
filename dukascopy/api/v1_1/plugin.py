#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        plugin.py
 Author:      JP Ueberbach
 Created:     2026-01-07
 Description: Plugin loading

 Requirements:
     - Python 3.8+
     - FastAPI
     - DuckDB

 License:
     MIT License
===============================================================================
"""
import os
import importlib.util
from pathlib import Path

def load_indicator_plugins():
    """Dynamically load indicator plugins from the plugin directory.

    This function scans the configured plugin directory for Python files,
    dynamically imports each valid module, and registers its ``calculate``
    function if present. Each plugin is keyed by its filename (without the
    ``.py`` extension).

    Returns:
        dict[str, callable]: A dictionary mapping plugin names to their
        corresponding ``calculate`` functions. If the plugin directory does
        not exist or no valid plugins are found, an empty dictionary is
        returned.

    """ 
    plugins = {}
    
    core_dir = Path(__file__).parent.parent / "plugins/indicators"
    user_dir = Path("config.user/plugins/indicators") # Specific user path
    
    search_dirs = [core_dir, user_dir]

    for plugin_dir in search_dirs:
        if not plugin_dir.exists():
            continue

        for file in os.listdir(plugin_dir):
            if file.endswith(".py") and not file.startswith("__"):
                plugin_name = file[:-3]
                file_path = plugin_dir / file
                
                # Dynamic Import
                spec = importlib.util.spec_from_file_location(plugin_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, "calculate"):
                    plugins[plugin_name] = module.calculate

    return plugins


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

    # Iterate through provided plugins by name
    for name, plugin in plugins.items():

        # Resolve the actual indicator function from the registry
        plugin_func = indicator_registry[name]

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


indicator_registry = load_indicator_plugins()