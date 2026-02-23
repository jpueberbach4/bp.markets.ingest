import yaml
from dataclasses import dataclass, fields, field
from typing import Dict, List, Optional, Type, TypeVar, Any
import glob
# Config loading optimization (currently responsible for 80 percent of startup lag)
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


@dataclass
class BuilderPaths:
    """Directory paths used by the script."""
    # Input directory
    data: str = "data"
    # Temporary directory
    temp: str = "data/temp/builder"

@dataclass
class BuilderConfig:
    """The root configuration for the builder.py script."""
    fmode: str = "binary"
    num_processes: Optional[int] = None
    paths: BuilderPaths = field(default_factory=BuilderPaths)

@dataclass
class AppConfig:
    """The root configuration for the entire application."""
    builder: BuilderConfig = field(default_factory=BuilderConfig)


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
        yaml_str = resolve_yaml_includes_to_string(file_path)
        # Parse the resolved YAML string into a Python dictionary
        yaml_data = yaml.load(yaml_str, Loader=SafeLoader)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {file_path}")
        return AppConfig() # Return default config if file is missing
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return AppConfig()
    
    # Load the parsed YAML data into the AppConfig object
    return load_config_data(AppConfig, yaml_data)
