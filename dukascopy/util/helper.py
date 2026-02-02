from util.discovery import *
from pathlib import Path
from util.config import load_app_config

def discover_all(options: Dict = {}):
    """Discovers all datasets based on the application configuration.

    This function loads the application configuration from a user-specific
    YAML file if it exists, otherwise it falls back to the default config.
    It then initializes a `DataDiscovery` instance using the builder
    configuration and scans the filesystem for available datasets.

    Args:
        options (Dict): A dictionary of optional parameters (currently unused).

    Returns:
        List[Dataset]: A list of Dataset instances found in the filesystem.
    """
    # Determine which configuration file to load: user-specific or default
    config_file_user = resolve_path('config.user.yaml')
    config_file_regular = resolve_path('config.yaml')

    config_file = config_file_user if Path(config_file_user).exists() else config_file_regular

    # Load the application configuration from the YAML file
    config = load_app_config(config_file)

    # Resolve config.builder.paths.data
    config.builder.paths.data = resolve_path(config.builder.paths.data)

    # Initialize the DataDiscovery instance with the builder configuration
    discovery = DataDiscovery(config.builder)

    # Scan the filesystem and return the discovered datasets
    return discovery.scan()

def resolve_path(path_str):
    if Path(path_str).exists():
        return path_str
    # the root path
    root_path = Path(__file__).parent.parent

    test_path = root_path / path_str
    if test_path.exists():
        return test_path
    
    # this will likely error out upstream
    return path_str
