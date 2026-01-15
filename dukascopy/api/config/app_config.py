from dataclasses import dataclass, fields, field
from typing import Dict, List, Optional, Type, TypeVar, Any

import yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

@dataclass
class HTTPServiceLimits:
    """Limits"""
    max_per_page: int = 100
    max_page: int = 1000

@dataclass
class HTTPServiceConfig:
    """The root configuration for the http-service script."""
    docs: str = "config/dukascopy/http-docs"
    listen: str = "127.0.0.1:8000"
    fmode: str = "binary"
    poolmode: str = "thread"
    limits: HTTPServiceLimits = field(default_factory=HTTPServiceLimits)

@dataclass
class AppConfig:
    """The root configuration for the entire application."""
    http: HTTPServiceConfig = field(default_factory=HTTPServiceConfig)

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
            yaml_data = yaml.load(f, Loader=SafeLoader)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {file_path}")
        return AppConfig() # Return default config if file is missing
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return AppConfig()
    
    # Load the parsed YAML data into the AppConfig object
    return load_config_data(AppConfig, yaml_data)
