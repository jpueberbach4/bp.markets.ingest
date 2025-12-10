import yaml
from dataclasses import dataclass, fields, field
from typing import Dict, List, Optional, Type, TypeVar, Any


@dataclass
class ResampleTimeframeConfig:
    """Configuration for a single resampled timeframe."""
    # Resampling rule (e.g., '5T', '1H'). None for the base timeframe.
    rule: Optional[str] = None
    # Label for interval alignment ('left' or 'right'). None for base timeframe.
    label: Optional[str] = None
    # Whether intervals are closed on the 'left' or 'right'. None for base timeframe.
    closed: Optional[str] = None
    # Source timeframe key or identifier.
    source: str = ""


@dataclass
class ResamplePaths:
    """Directory paths used by the script."""
    # Output directory for resampling results.
    data: str = "data/resample"


@dataclass
class ResampleSymbolOverride:
    """Per-symbol configuration overrides."""
    # Number of decimals to round to.
    round_decimals: Optional[int] = None
    # Number of lines to read per batch for this symbol.
    batch_size: Optional[int] = None
    # List of timeframes to skip for this symbol.
    skip_timeframes: List[str] = field(default_factory=list)
    # Mapping: timeframe name -> timeframe config.
    timeframes: Dict[str, ResampleTimeframeConfig] = field(default_factory=dict)


@dataclass
class ResampleConfig:
    """The root configuration for the resample.py script."""
    round_decimals: int = 8
    batch_size: int = 250_000
    paths: ResamplePaths = field(default_factory=ResamplePaths)
    # Mapping: timeframe name -> timeframe config.
    timeframes: Dict[str, ResampleTimeframeConfig] = field(default_factory=dict)
    # Mapping: symbol name -> symbol-specific overrides.
    symbols: Dict[str, ResampleSymbolOverride] = field(default_factory=dict)

@dataclass
class AggregatePaths:
    """Directory paths used by the script."""
    # Output directory for aggregate results.
    data: str = "data/aggregate/1m"
    # Input directory of transform results (historic)
    historic: str = "data/transform/1m"
    # Input directory of transform results (live)
    live: str = "data/temp"

@dataclass
class AggregateConfig:
    """The root configuration for the aggregate.py script."""
    paths: AggregatePaths = field(default_factory=AggregatePaths)

@dataclass
class DownloadPaths:
    """Directory paths used by the script."""
    # Output directory for historic downloads
    historic: str = "cache"
    # Output directory of live downloads
    live: str = "data/temp"

@dataclass
class DownloadConfig:
    """The root configuration for the download.py script."""
    max_retries: int = 3
    backoff_factor: int = 2
    timeout: int = 10
    rate_limit_rps: float = 0.5
    paths: DownloadPaths = field(default_factory=DownloadPaths)

@dataclass
class TransformPaths:
    """Directory paths used by the script."""
    # How much ms should we shift time by (0=UTC, 7200000=GMT+2)
    time_shift_ms: int = 0
    # Input directory for historic
    historic: str = "cache"
    # Output directory for transform of historic
    data: str = "data/transform/1m"
    # Input/Output directory of live
    live: str = "data/temp"

@dataclass
class TransformConfig:
    """The root configuration for the download.py script."""
    round_decimals: int = 10
    paths: TransformPaths = field(default_factory=TransformPaths)

@dataclass
class AppConfig:
    """The root configuration for the entire application."""
    aggregate: AggregateConfig = field(default_factory=AggregateConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    resample: ResampleConfig = field(default_factory=ResampleConfig)
    transform: TransformConfig = field(default_factory=TransformConfig)

#--- Load functionality ---
T = TypeVar('T')

def load_config_data(config_class: Type[T], data: Dict[str, Any]) -> T:
    """
    Recursively maps a dictionary (from YAML) to a nested dataclass structure.
    """
    # Get the expected fields and their types from the dataclass
    field_definitions = {f.name: f.type for f in fields(config_class)}
    
    # Final dictionary to hold arguments for the dataclass constructor
    final_args: Dict[str, Any] = {}

    for name, value in data.items():
        if name not in field_definitions:
            # Skip fields in the YAML not defined in the dataclass
            continue

        field_type = field_definitions[name]
        
        # Check if the field is a nested dataclass (Type[T] is a dataclass)
        if hasattr(field_type, '__dataclass_fields__'):
            # Recursively call load for the nested dataclass
            final_args[name] = load_config_data(field_type, value)
        
        # Check if the field is a Dictionary mapping keys to a nested dataclass 
        elif getattr(field_type, '__origin__', None) is dict:
            key_type, value_type = field_type.__args__
            
            if hasattr(value_type, '__dataclass_fields__'):
                # Map the dictionary values recursively
                nested_data = {
                    k: load_config_data(value_type, v) 
                    for k, v in value.items()
                }
                final_args[name] = nested_data
            else:
                # Handle Dict[str, str] or other simple dicts
                final_args[name] = value

        # Otherwise, assume it's a primitive type or list and assign directly
        else:
            final_args[name] = value

    return config_class(**final_args)


def load_app_config(file_path: str = 'config.yaml') -> AppConfig:
    """Loads configuration from a YAML file into the AppConfig dataclass."""
    try:
        with open(file_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {file_path}")
        return AppConfig() # Return default config if file is missing
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return AppConfig()
    
    # Load the parsed YAML data into the AppConfig object
    return load_config_data(AppConfig, yaml_data)
