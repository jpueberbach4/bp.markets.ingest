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
from typing import Dict, List, Optional, Type, TypeVar, Any, Union, get_origin, get_args


@dataclass
class ResampleSymbolTradingSessionRange:
    """Defines the 'from' and 'to' times for a single time range."""
    from_time: str = field(metadata={'yaml_key': 'from'}) 
    to_time: str = field(metadata={'yaml_key': 'to'})


@dataclass
class ResampleSymbolTradingSession:
    """
    Configuration for a single named session (e.g., 'day-session').
    """
    ranges: Dict[str, ResampleSymbolTradingSessionRange] = field(default_factory=dict)
    timeframes: Dict[str, 'ResampleTimeframeConfig'] = field(default_factory=dict)

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
    timezone: str = ""
    sessions: Dict[str, ResampleSymbolTradingSession] = field(default_factory=dict, metadata={'yaml_key': 'sessions'})


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

# AI generated but manually adjusted
def load_config_data(config_class: Type[T], data: Dict[str, Any]) -> T:
    """
    Recursively map a dictionary into a nested dataclass structure.

    Includes robust handling for Optional, nested Dataclasses, Dicts of Dataclasses,
    and string forward references.
    """
    # Collect declared field names and types from the target dataclass
    field_definitions = {f.name: f.type for f in fields(config_class)}

    # Arguments to be passed into the dataclass constructor
    final_args: Dict[str, Any] = {}

    # Global scope is used to resolve forward-referenced types (string annotations)
    global_scope = globals()

    for name, value in data.items():
        # Map YAML key to dataclass field name (via metadata override if present)
        field_name = name
        found_field = next(
            (f for f in fields(config_class) if f.metadata.get("yaml_key") == name),
            None
        )
        if found_field:
            field_name = found_field.name
        elif name not in field_definitions:
            # Ignore unknown keys in the input data
            continue

        field_type = field_definitions[field_name]

        # Unwrap Optional[T] / Union[T, None] to get the underlying type
        unwrapped_type = field_type
        if get_origin(field_type) is Union:
            args = [a for a in get_args(field_type) if a is not type(None)]
            if args:
                unwrapped_type = args[0]

        # Case 1: Field is a nested dataclass
        if hasattr(unwrapped_type, "__dataclass_fields__"):
            if value is not None:
                # Recursively construct the nested dataclass
                final_args[field_name] = load_config_data(unwrapped_type, value)
            else:
                # Preserve None for Optional[Dataclass]
                final_args[field_name] = None
            continue

        # Case 2: Field is a dictionary (possibly mapping to dataclasses)
        origin = get_origin(unwrapped_type)
        if origin is dict:
            if value is None:
                # Normalize missing dictionaries to empty dicts
                final_args[field_name] = {}
                continue

            args = get_args(field_type)
            if len(args) == 2:
                value_type = args[1]

                # Resolve forward-referenced value types
                if isinstance(value_type, str):
                    value_type = global_scope.get(value_type)

                if value_type is not None and hasattr(value_type, "__dataclass_fields__"):
                    # Dict[str, Dataclass] → recursively load each value
                    final_args[field_name] = {
                        k: load_config_data(value_type, v)
                        for k, v in value.items()
                    }
                    continue

            # Fallback for Dict[str, primitive] or unsupported value types
            final_args[field_name] = value

        # Case 3: Primitive types, lists, or other generics
        else:
            final_args[field_name] = value

    # Instantiate and return the populated dataclass
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
