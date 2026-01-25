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
    config_file = 'config.user.yaml' if Path('config.user.yaml').exists() else 'config.yaml'

    # Load the application configuration from the YAML file
    config = load_app_config(config_file)

    # Initialize the DataDiscovery instance with the builder configuration
    discovery = DataDiscovery(config.builder)

    # Scan the filesystem and return the discovered datasets
    return discovery.scan()