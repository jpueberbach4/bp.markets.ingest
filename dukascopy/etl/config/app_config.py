#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        app_config.py
 Author:      JP Ueberbach
 Created:     2025-11-09
 Description: Application configuration loader and YAML include resolver.

              This module defines the dataclass-based configuration schema for 
              the application (download, transform, resample, aggregate) and 
              provides utilities to:

              - Load YAML configuration files
              - Recursively resolve `includes` directives in YAML
              - Map parsed YAML dictionaries into strongly-typed dataclass structures

              Note: Heavily AI-assisted boilerplate code. 
              
 Requirements:
     - Python 3.8+
 
 License:
     MIT License
===============================================================================
"""
import yaml
import glob
from dataclasses import dataclass, fields, field
from typing import Dict, List, Optional, Type, TypeVar, Any


@dataclass
class ResampleTimeframeConfig:
    """Configuration for a single resampled timeframe."""
    rule: Optional[str] = None
    label: Optional[str] = None
    closed: Optional[str] = None
    origin: str = "epoch"
    source: str = ""


@dataclass
class ResamplePaths:
    """Filesystem paths used by the resampling pipeline."""
    data: str = "data/resample"


@dataclass
class ResampleSymbolOverride:
    """Per-symbol overrides for resampling behavior."""
    round_decimals: Optional[int] = None
    batch_size: Optional[int] = None
    skip_timeframes: List[str] = field(default_factory=list)
    timeframes: Dict[str, ResampleTimeframeConfig] = field(default_factory=dict)


@dataclass
class ResampleConfig:
    """Root configuration for the resampling stage."""
    round_decimals: int = 8
    batch_size: int = 250_000
    paths: ResamplePaths = field(default_factory=ResamplePaths)
    timeframes: Dict[str, ResampleTimeframeConfig] = field(default_factory=dict)
    symbols: Dict[str, ResampleSymbolOverride] = field(default_factory=dict)


@dataclass
class AggregatePaths:
    """Filesystem paths used by the aggregation pipeline."""
    data: str = "data/aggregate/1m"
    historic: str = "data/transform/1m"
    live: str = "data/temp"


@dataclass
class AggregateConfig:
    """Root configuration for the aggregation stage."""
    paths: AggregatePaths = field(default_factory=AggregatePaths)


@dataclass
class DownloadPaths:
    """Filesystem paths used by the download pipeline."""
    historic: str = "cache"
    live: str = "data/temp"


@dataclass
class DownloadConfig:
    """Root configuration for the download stage."""
    max_retries: int = 3
    backoff_factor: int = 2
    timeout: int = 10
    rate_limit_rps: float = 0.5
    paths: DownloadPaths = field(default_factory=DownloadPaths)


@dataclass
class TransformTimezone:
    """Timezone-specific MT4 shift configuration."""
    offset_to_shift_map: Dict[int, int] = field(default_factory=dict)
    symbols: List[str] = field(default_factory=list)


@dataclass
class TransformPaths:
    """Filesystem paths used by the transform pipeline."""
    historic: str = "cache"
    data: str = "data/transform/1m"
    live: str = "data/temp"


@dataclass
class TransformConfig:
    """Root configuration for the transform stage."""
    time_shift_ms: int = 0
    round_decimals: int = 10
    paths: TransformPaths = field(default_factory=TransformPaths)
    timezones: Dict[str, TransformTimezone] = field(default_factory=dict)


@dataclass
class AppConfig:
    """Top-level application configuration."""
    aggregate: AggregateConfig = field(default_factory=AggregateConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    resample: ResampleConfig = field(default_factory=ResampleConfig)
    transform: TransformConfig = field(default_factory=TransformConfig)


T = TypeVar("T")


def load_config_data(config_class: Type[T], data: Dict[str, Any]) -> T:
    """
    Recursively map a dictionary into a nested dataclass structure.

    Unknown fields in the input dictionary are ignored. Nested dataclasses
    and dictionaries of dataclasses are handled automatically.
    """
    # Map field names to their declared types
    field_definitions = {f.name: f.type for f in fields(config_class)}
    final_args: Dict[str, Any] = {}

    for name, value in data.items():
        # Skip unknown configuration keys
        if name not in field_definitions:
            continue

        field_type = field_definitions[name]

        # Nested dataclass
        if hasattr(field_type, "__dataclass_fields__"):
            final_args[name] = load_config_data(field_type, value)

        # Dictionary field (possibly mapping to dataclasses)
        elif getattr(field_type, "__origin__", None) is dict:
            _, value_type = field_type.__args__
            if hasattr(value_type, "__dataclass_fields__"):
                final_args[name] = {
                    k: load_config_data(value_type, v)
                    for k, v in value.items()
                }
            else:
                final_args[name] = value

        # Primitive or list field
        else:
            final_args[name] = value

    return config_class(**final_args)


def _resolve_yaml_includes(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolve `includes` directives in a YAML-loaded dictionary.

    Any dictionary containing an `includes` key will:
    - Load all matching YAML files
    - Merge them in order
    - Overlay inline configuration on top
    """
    if not isinstance(data, dict):
        return data

    for key, value in list(data.items()):
        if isinstance(value, dict):
            # Resolve includes at this level
            if "includes" in value and isinstance(value["includes"], list):
                includes_list: List[str] = value.pop("includes")
                merged_data: Dict[str, Any] = {}

                # Load and merge included YAML files
                for pattern in includes_list:
                    for file_path in glob.glob(pattern):
                        try:
                            with open(file_path, "r") as f:
                                included_data = yaml.safe_load(f)
                                if isinstance(included_data, dict):
                                    merged_data.update(included_data)
                        except (FileNotFoundError, yaml.YAMLError):
                            pass

                # Overlay inline configuration
                merged_data.update(value)
                data[key] = merged_data

            # Recurse into nested dictionaries
            _resolve_yaml_includes(data[key])

        elif isinstance(value, list):
            # Recurse into dictionaries inside lists
            for item in value:
                if isinstance(item, dict):
                    _resolve_yaml_includes(item)

    return data


def resolve_yaml_includes_to_string(config_file_path: str) -> str:
    """
    Load a YAML file, resolve all `includes`, and return the merged YAML as a string.
    """
    try:
        with open(config_file_path, "r") as f:
            yaml_data = yaml.safe_load(f)
    except FileNotFoundError:
        return f"Error: Configuration file not found at {config_file_path}"
    except yaml.YAMLError as e:
        return f"Error parsing YAML file: {e}"

    if not isinstance(yaml_data, dict):
        return "Error: Top level of YAML file must be a dictionary."

    # Resolve includes recursively
    resolved_data = _resolve_yaml_includes(yaml_data)

    # Serialize back to YAML
    return yaml.safe_dump(
        resolved_data,
        default_flow_style=False,
        sort_keys=False,
    )


def load_app_config(file_path: str = "config.yaml") -> AppConfig:
    """
    Load the application configuration from a YAML file into an AppConfig object.

    Includes are resolved before parsing. If loading fails, a default AppConfig
    is returned.
    """
    try:
        yaml_str = resolve_yaml_includes_to_string(file_path)
        yaml_data = yaml.safe_load(yaml_str)
    except (FileNotFoundError, yaml.YAMLError):
        return AppConfig()

    return load_config_data(AppConfig, yaml_data)
