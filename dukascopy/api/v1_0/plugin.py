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
    plugin_dir = Path(__file__).parent / "plugins"
    if not plugin_dir.exists():
        return plugins

    for file in os.listdir(plugin_dir):
        if file.endswith(".py") and not file.startswith("__"):
            plugin_name = file[:-3]
            file_path = plugin_dir / file
            
            spec = importlib.util.spec_from_file_location(plugin_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "calculate"):
                plugins[plugin_name] = module.calculate

    return plugins