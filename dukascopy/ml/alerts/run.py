"""
===============================================================================
File:        run.py
Author:      JP Ueberbach
Created:     2026-03-03

Description:
    Entry point module for launching the ML alert processing engine.

    This module is responsible for:
        - Locating and loading the appropriate application configuration file
        - Extracting ML alert configuration settings
        - Initializing the AlertEngine with the resolved configuration
        - Executing the engine job processing loop
        - Handling top-level runtime exceptions gracefully

    Configuration Resolution Order:
        1. config.user.yaml (preferred if present)
        2. config.yaml (fallback)

    The module is designed to be executed as a script and serves as the
    orchestration layer between configuration management and the ML alerts
    processing engine.
===============================================================================
"""

import os
from ml.alerts.engine import AlertEngine
from util.config import load_app_config


def main():
    """
    Application entry point.

    This function performs the following steps:

    1. Defines the configuration file resolution order.
    2. Selects the first configuration file that exists on disk.
    3. Loads the application configuration.
    4. Extracts the ML alerts configuration section.
    5. Instantiates the AlertEngine with the alerts configuration.
    6. Executes the engine job processing loop.
    7. Catches and logs any unhandled exceptions from the engine loop.

    Raises:
        IndexError: If no configuration file is found in the resolution list.
        Exception: Propagates unexpected errors during configuration loading
                   before engine initialization.
    """

    # Define configuration file precedence (user override first, default second)
    paths = [
        "config.user.yaml",
        "config.yaml",
    ]

    # Select the first existing configuration file from the resolution list
    # This ensures user-specific configuration overrides the default when present
    config_path = [p for p in paths if os.path.isfile(p)][0]

    # Load the application configuration using the resolved configuration path
    # The returned object is expected to expose structured configuration access
    app_config = load_app_config(config_path)

    # Extract the ML alerts configuration subsection
    # Uses safe dictionary-style access to avoid direct attribute dependency
    alerts_config = app_config.ml.get("alerts")

    # Instantiate the AlertEngine with the resolved alerts configuration
    # The engine encapsulates job orchestration and processing logic
    engine = AlertEngine(alerts_config)

    try:
        # Start the engine job processing loop
        # This call is expected to block while processing alert jobs
        engine.process_jobs()
    except Exception as e:
        # Catch any unhandled exception from the engine loop
        # Prevents abrupt termination without error visibility
        print(f"[System Error] Engine loop failed: {e}")


if __name__ == "__main__":
    # Execute the application entry point only when run as a script
    # Prevents automatic execution when imported as a module
    main()