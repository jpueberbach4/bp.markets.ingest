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

    indicators = {}
    for name, plugin in plugins.items():

        # Get plugin function
        plugin_func = indicator_registry[name]

        # Initialize indicator options with raw positional parameters
        info = {
            "name": name,
            "description": "N/A",
            "warmup": 0,
            "defaults": {},
            "meta": {}
        }

        # Map positional arguments if the plugin defines a mapper
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            info['defaults'].update(plugin_func.__globals__["position_args"]([]))

        # Query the plugin for its warmup row requirement, if defined
        if hasattr(plugin_func, "__globals__") and "warmup_count" in plugin_func.__globals__:
            info['warmup'] = plugin_func.__globals__["warmup_count"](info['defaults'])

        # Query the plugin for its description, if defined
        if hasattr(plugin_func, "__globals__") and "description" in plugin_func.__globals__:
            info['description'] = plugin_func.__globals__["description"]()

        # Query the plugin for its metadata, if defined
        if hasattr(plugin_func, "__globals__") and "meta" in plugin_func.__globals__:
            info['meta'].update(plugin_func.__globals__["meta"]())

        indicators[name] = info


    sorted_data = {k: indicators[k] for k in sorted(indicators)}
    return sorted_data

indicator_registry = load_indicator_plugins()