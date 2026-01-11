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
import glob
import copy
import jsonschema
import orjson
from jsonschema import validate
from dataclasses import dataclass, fields, field
from pathlib import Path
from typing import Dict, List, Optional, Type, TypeVar, Any, Union, get_origin, get_args
from etl.exceptions import *

# Config loading optimization (currently responsible for 80 percent of startup lag)
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper

import fastjsonschema
def _get_validator():
    schema_path = Path(__file__).parent.resolve() / "schema.json"
    with open(schema_path, "rb") as f:
        schema = orjson.loads(f.read())
    return fastjsonschema.compile(schema)

VALIDATE_CONFIG = _get_validator()


@dataclass
class ResampleTimeRange:
    """Defines the 'from' and 'to' times for a single time range."""
    from_time: str = field(default="00:00",metadata={'yaml_key': 'from'}) 
    to_time: str = field(default="23:59",metadata={'yaml_key': 'to'})


@dataclass
class ResampleDateRange:
    """Defines the 'from' and 'to' dates for a single date range."""
    weekdays: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6]) # default to all weekdays
    from_date: str = field(default=None,metadata={'yaml_key': 'from_date'}) 
    to_date: str = field(default=None,metadata={'yaml_key': 'to_date'})


@dataclass
class ResampleSymbolTradingSession(ResampleDateRange):
    """
    Configuration for a single named session (e.g., 'day-session').
    """
    ranges: Dict[str, ResampleTimeRange] = field(default_factory=dict)
    timeframes: Dict[str, 'ResampleTimeframe'] = field(default_factory=dict)


@dataclass
class ResampleTimeframeProcessingStep(ResampleDateRange):
    """
    Configuration for a pre/post processing step
    """
    action: str = field(default=None,metadata={'yaml_key': 'action'}) 
    ends_with: Optional[str] = field(default=None, metadata={'yaml_key': 'ends_with'}) 
    offset: int = field(default=-1, metadata={'yaml_key': 'offset'})


@dataclass
class ResampleTimeframe:
    """Configuration for a single resampled timeframe."""
    rule: Optional[str] = None
    label: Optional[str] = None
    closed: Optional[str] = None
    origin: str = "epoch"
    source: Optional[str] = None
    pre: Optional[Dict[str, ResampleTimeframeProcessingStep]] = field(default=None)
    post: Optional[Dict[str, ResampleTimeframeProcessingStep]] = field(default=None)


@dataclass
class ResamplePaths:
    """Filesystem paths used by the resampling pipeline."""
    data: str = "data/resample"


@dataclass
class ResampleSymbol:
    """Per-symbol overrides for resampling behavior."""
    round_decimals: Optional[int] = None
    batch_size: Optional[int] = None
    fsync: Optional[bool] = None
    fmode: Optional[str] = None
    skip_timeframes: List[str] = field(default_factory=list)
    timeframes: Dict[str, ResampleTimeframe] = field(default_factory=dict)
    timezone: str = ""
    server_timezone: str = ""
    sessions: Dict[str, ResampleSymbolTradingSession] = field(default_factory=dict, metadata={'yaml_key': 'sessions'})


@dataclass
class ResampleConfig:
    """Root configuration for the resampling stage."""
    round_decimals: int = 8
    batch_size: int = 250_000
    fmode: str = "text"
    fsync: bool = False
    paths: ResamplePaths = field(default_factory=ResamplePaths)
    timeframes: Dict[str, ResampleTimeframe] = field(default_factory=dict)
    symbols: Dict[str, ResampleSymbol] = field(default_factory=dict)


@dataclass
class AggregatePaths:
    """Filesystem paths used by the aggregation pipeline."""
    data: str = "data/aggregate/1m"
    historic: str = "data/transform/1m"
    live: str = "data/temp"


@dataclass
class AggregateConfig:
    """Root configuration for the aggregation stage."""
    fsync: bool = False
    fmode: str = "text"
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
class TransformSymbolProcessingStep:
    """
    Configuration for a pre/post processing step
    """
    action: str = field(default=None,metadata={'yaml_key': 'action'}) 
    column: str = field(default=None,metadata={'yaml_key': 'column'}) 
    value: int = field(default=None, metadata={'yaml_key': 'value'})

@dataclass
class TransformSymbol:
    """Per-symbol overrides for resampling behavior."""
    post: Optional[Dict[str, TransformSymbolProcessingStep]] = field(default=None)

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
    fmode: Optional[str] = None
    fsync: bool = False
    validate: bool = False
    paths: TransformPaths = field(default_factory=TransformPaths)
    timezones: Dict[str, TransformTimezone] = field(default_factory=dict)
    symbols: Dict[str, TransformSymbol] = field(default_factory=dict)


@dataclass
class OrchestratorPaths:
    """Filesystem paths used by the transform pipeline."""
    downloads: str = "cache"
    transforms: str = "data/transform/1m"
    locks: str = "data/locks"

@dataclass
class OrchestratorConfig:
    """Root configuration for the orchestrator."""
    num_processes: Optional[int] = None
    paths: OrchestratorPaths = field(default_factory=OrchestratorPaths)


@dataclass
class AppConfig:
    """Top-level application configuration."""
    aggregate: AggregateConfig = field(default_factory=AggregateConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    resample: ResampleConfig = field(default_factory=ResampleConfig)
    transform: TransformConfig = field(default_factory=TransformConfig)


T = TypeVar("T")

# AI generated but manually adjusted
def load_config_data(config_class: Type[T], data: Dict[str, Any]) -> T:
    """
    Recursively load a dictionary into a nested dataclass structure.

    This function supports:
        - Optional fields (Union[T, None])
        - Nested dataclasses
        - Dict fields where values may be dataclasses
        - Forward-referenced types (string annotations)

    Parameters
    ----------
    config_class : Type[T]
        The dataclass type to populate.
    data : Dict[str, Any]
        The dictionary containing configuration data.

    Returns
    -------
    T
        An instance of `config_class` with fields populated from `data`.
    """

    # Map field names to their types for the target dataclass
    field_definitions = {f.name: f.type for f in fields(config_class)}

    # Store arguments for dataclass constructor
    final_args: Dict[str, Any] = {}

    # Global scope used to resolve string type hints
    global_scope = globals()

    for name, value in data.items():
        # Resolve YAML key mapping to dataclass field
        field_name = name
        found_field = next(
            (f for f in fields(config_class) if f.metadata.get("yaml_key") == name),
            None
        )
        if found_field:
            field_name = found_field.name
        elif name not in field_definitions:
            # Skip keys not defined in dataclass
            continue

        field_type = field_definitions[field_name]

        # Unwrap Optional[T] types
        unwrapped_type = field_type
        if get_origin(field_type) is Union:
            args = [a for a in get_args(field_type) if a is not type(None)]
            if args:
                unwrapped_type = args[0]

        # Nested dataclass handling
        if hasattr(unwrapped_type, "__dataclass_fields__"):
            if value is not None:
                final_args[field_name] = load_config_data(unwrapped_type, value)
            else:
                final_args[field_name] = None
            continue

        # Dict field handling
        origin = get_origin(unwrapped_type)
        if origin is dict:
            if value is None:
                final_args[field_name] = {}
                continue

            args = get_args(field_type)
            if len(args) == 2:
                value_type = args[1]

                # Resolve forward-referenced types
                if isinstance(value_type, str):
                    value_type = global_scope.get(value_type)

                # Recursively load dict values if they are dataclasses
                if value_type is not None and hasattr(value_type, "__dataclass_fields__"):
                    final_args[field_name] = {
                        k: load_config_data(value_type, v)
                        for k, v in value.items()
                    }
                    continue

            # Fallback: keep original dictionary
            final_args[field_name] = value
        else:
            # Primitive or generic field
            final_args[field_name] = value

    # Construct the dataclass instance
    return config_class(**final_args)




def _resolve_yaml_includes(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolve `includes` directives in a YAML-loaded dictionary.

    Any dictionary containing an `includes` key with a list of file patterns
    will have those files loaded and merged in order. The inline configuration
    in the current dictionary always takes precedence over included data.

    Parameters
    ----------
    data : Dict[str, Any]
        A dictionary produced by loading a YAML file.

    Returns
    -------
    Dict[str, Any]
        The same dictionary structure with all `includes` resolved and merged.
    """
    # Non-dict values are returned as-is (base case for recursion)
    if not isinstance(data, dict):
        return data

    # Iterate over a snapshot of items to allow in-place mutation
    for key, value in list(data.items()):
        if isinstance(value, dict):
            # Check for an `includes` directive at this level
            if "includes" in value and isinstance(value["includes"], list):
                # Extract include patterns and remove the directive
                includes_list: List[str] = value.pop("includes")
                merged_data: Dict[str, Any] = {}

                # Load and merge all included YAML files in order
                for pattern in includes_list:
                    for file_path in glob.glob(pattern):
                        try:
                            with open(file_path, "r") as f:
                                included_data = yaml.load(f,Loader=SafeLoader)
                                if isinstance(included_data, dict):
                                    merged_data.update(included_data)
                        except (FileNotFoundError, yaml.YAMLError):
                            # Ignore missing or invalid include files
                            pass

                # Overlay inline configuration on top of included data
                merged_data.update(value)
                data[key] = merged_data

            # Recurse into the (possibly merged) dictionary
            _resolve_yaml_includes(data[key])

        elif isinstance(value, list):
            # Recurse into any dictionaries contained within lists
            for item in value:
                if isinstance(item, dict):
                    _resolve_yaml_includes(item)

    return data

def resolve_yaml_includes_to_string(config_file_path: str) -> str:
    """
    Load a YAML configuration file, resolve all nested `includes`, and return
    the fully merged configuration as a YAML string.

    This function reads the YAML file from disk, expands any `includes` keys
    by recursively loading and merging referenced YAML files, and then
    serializes the final configuration back into a YAML-formatted string.

    Parameters
    ----------
    config_file_path : str
        Path to the root YAML configuration file.

    Returns
    -------
    str
        The resolved YAML configuration as a string, or an error message
        if loading or parsing fails.
    """
    # Load the root YAML configuration file
    try:
        with open(config_file_path, "r") as f:
            yaml_data = yaml.load(f, Loader=SafeLoader)
    except FileNotFoundError:
        return f"Error: Configuration file not found at {config_file_path}"
    except yaml.YAMLError as e:
        return f"Error parsing YAML file: {e}"

    # The top-level YAML structure must be a dictionary
    if not isinstance(yaml_data, dict):
        return "Error: Top level of YAML file must be a dictionary."

    # Recursively resolve all `includes` directives
    resolved_data = _resolve_yaml_includes(yaml_data)

    # Serialize the resolved configuration back into a YAML string
    return yaml.dump(
        resolved_data,
        default_flow_style=False,
        sort_keys=False,
        Dumper=SafeDumper
    )



def resample_get_symbol_config(symbol: str, app_config: AppConfig) -> ResampleSymbol:
    """Build and resolve the final resampling configuration for a symbol.

    This function merges global resampling defaults with symbol-level overrides,
    resolves session-specific configurations, normalizes timeframe processing
    steps, and applies final skip rules.

    Args:
        symbol: Trading symbol identifier (e.g., "BTCUSDT").
        app_config: Global application configuration containing resample settings.

    Returns:
        A fully resolved ResampleSymbol configuration for the given symbol.
    """
    # Work on a deep copy to avoid mutating the global application config
    merged_config: ResampleConfig = copy.deepcopy(app_config.resample)

    # Ensure the symbol exists in the config map
    if symbol not in merged_config.symbols:
        merged_config.symbols[symbol] = ResampleSymbol()

    symbol_override = merged_config.symbols[symbol]

    # Inherit scalar defaults from the global config when not explicitly set
    symbol_override.round_decimals = (
        symbol_override.round_decimals or merged_config.round_decimals
    )
    symbol_override.batch_size = (
        symbol_override.batch_size or merged_config.batch_size
    )
    # Optional fsync safety feature (forces flushing to disk)
    if symbol_override.fsync is None:
        symbol_override.fsync = merged_config.fsync
        
    # fmode (binary or text), inherit from global
    symbol_override.fmode = merged_config.fmode

    def normalize_tf(tf: ResampleTimeframe) -> ResampleTimeframe:
        """Normalize timeframe pre/post processing steps.

        Converts raw dictionary-based processing step definitions into
        ResampleTimeframeProcessingStep dataclass instances.

        Args:
            tf: Timeframe configuration to normalize.

        Returns:
            The normalized ResampleTimeframe instance.
        """
        for attr in ["pre", "post"]:
            val = getattr(tf, attr)
            if val is not None and isinstance(val, dict):
                normalized_steps = {}
                for step_name, step_data in val.items():
                    # Convert step definitions into dataclass instances if needed
                    if isinstance(step_data, dict):
                        normalized_steps[step_name] = (
                            ResampleTimeframeProcessingStep(**step_data)
                        )
                    else:
                        normalized_steps[step_name] = step_data
                setattr(tf, attr, normalized_steps)
        return tf

    def merge_timeframes(
        base_map: Dict[str, ResampleTimeframe],
        override_map: Dict[str, Any],
    ):
        """Merge timeframe overrides into a base timeframe map.

        Only non-None fields from the override are applied. Empty pre/post
        dictionaries are ignored to prevent wiping populated configurations.

        Args:
            base_map: Base timeframe configurations to be modified in place.
            override_map: Override timeframe definitions.
        """
        for tf_name, tf_val in override_map.items():
            # Convert raw dict overrides into ResampleTimeframe objects
            if isinstance(tf_val, dict):
                tf_val = ResampleTimeframe(**tf_val)

            # Normalize pre/post processing steps
            tf_val = normalize_tf(tf_val)

            if tf_name in base_map:
                target_tf = base_map[tf_name]

                # Selectively override only non-None fields
                for f in fields(ResampleTimeframe):
                    new_val = getattr(tf_val, f.name)
                    if new_val is not None:
                        # Prevent empty pre/post dicts from erasing populated ones
                        if f.name in ["pre", "post"] and not new_val:
                            continue
                        setattr(target_tf, f.name, new_val)
            else:
                # New timeframe definition
                base_map[tf_name] = tf_val

    # Merge symbol-level timeframe overrides into global defaults
    base_tfs = copy.deepcopy(merged_config.timeframes)
    merge_timeframes(base_tfs, symbol_override.timeframes)
    symbol_override.timeframes = base_tfs

    # Resolve trading sessions
    if not symbol_override.sessions:
        # Create a default 24h session if none are defined
        default_range = ResampleTimeRange(
            from_time="00:00:00",
            to_time="23:59:59",
        )
        symbol_override.sessions = {
            "default": ResampleSymbolTradingSession(
                ranges={"default": default_range},
                timeframes=copy.deepcopy(symbol_override.timeframes),
            )
        }
    else:
        # Merge session-specific timeframe overrides
        for sess_name, session in symbol_override.sessions.items():
            s_tfs = copy.deepcopy(symbol_override.timeframes)
            merge_timeframes(s_tfs, session.timeframes)
            session.timeframes = s_tfs
            # make sure we copy the from_date, to_date and weekdays into the processing steps
            # this makes sure that any processing steps defined on session level are 
            # confined by the time-related boundaries of the session
            for tf_name, timeframe in session.timeframes.items():
                if timeframe.pre:
                    for s_name, step in timeframe.pre.items():
                        step.from_date, step.to_date, step.weekdays = \
                            [session.from_date, session.to_date, session.weekdays] 
                if timeframe.post:
                    for s_name, step in timeframe.post.items():
                        step.from_date, step.to_date, step.weekdays = \
                            [session.from_date, session.to_date, session.weekdays] 

    # Apply final skip logic to remove unwanted timeframes
    for ident in symbol_override.skip_timeframes:
        for session in symbol_override.sessions.values():
            session.timeframes.pop(ident, None)
        symbol_override.timeframes.pop(ident, None)

    # Find the symbols server-timezone
    # Bit hacky, but we need to check transform config for this
    # Seperation of concerns broken
    for name, timezone in app_config.transform.timezones.items():
        # Check whether the symbol or the wildcard '*' belongs to this timezone group
        if symbol in timezone.symbols or '*' in timezone.symbols:
            symbol_override.server_timezone = name
            break       

    return symbol_override




def load_app_config(file_path: str = "config.yaml") -> AppConfig:
    """
    Load the full application configuration from a YAML file.

    This function resolves any YAML `includes`, parses the resulting configuration,
    and maps it into the strongly-typed `AppConfig` dataclass hierarchy. If loading
    or parsing fails for any reason, a default `AppConfig` instance is returned to
    allow the application to continue running with safe defaults.

    Parameters
    ----------
    file_path : str, optional
        Path to the root YAML configuration file. Defaults to "config.yaml".

    Returns
    -------
    AppConfig
        Fully populated application configuration object, or a default instance
        if an error occurs during loading.
    """
    # Resolve YAML includes and load the merged YAML content as a string
    try:
        yaml_str = resolve_yaml_includes_to_string(file_path)
        # Parse the resolved YAML string into a Python dictionary
        yaml_data = yaml.load(yaml_str, Loader=SafeLoader)

        # Load JSON Schema
        schema_path = Path(__file__).parent.resolve() / "schema.json"
        with open(schema_path, "rb") as f:
            schema = orjson.loads(f.read())

        try:
            # Use the pre-compiled fast validator
            VALIDATE_CONFIG(yaml_data) 
        except fastjsonschema.JsonSchemaException as e:
            raise ConfigurationError(f"Configuration invalid {list(e.path)}: {e.message}")

    except (FileNotFoundError, yaml.YAMLError):
        # Fall back to default configuration if loading or parsing fails
        return AppConfig()

    # Map the parsed configuration dictionary into the AppConfig dataclass
    return load_config_data(AppConfig, yaml_data)

