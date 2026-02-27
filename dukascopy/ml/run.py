"""
===============================================================================
File:        run.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Application entry point for launching a ML universe.

    This module is responsible for:
        - Parsing command-line arguments
        - Resolving and loading application configuration
        - Instantiating the configured Universe, Singularity, and Flight
        - Bootstrapping the execution lifecycle from data ingestion
          to evolutionary optimization

    The module acts as the outermost orchestration layer, wiring together
    all major subsystems using factory abstractions and a config-driven
    approach. No domain logic is implemented here—only coordination.

Key Capabilities:
    - Command-line driven universe selection
    - Automatic configuration file discovery
    - Factory-based instantiation of core ML components
    - Deterministic startup sequence for reproducible runs
===============================================================================
"""
from util.config import load_app_config
from typing import Dict, Any
import os
import argparse


def parse_args() -> Dict[str, Any]:
    """
    Parse command-line arguments.

    Currently supports selecting which universe configuration
    should be initialized and executed.

    Returns:
        Dict[str, Any]:
            Dictionary containing parsed runtime arguments,
            including the selected universe name.
    """
    parser = argparse.ArgumentParser(
        description="Event Horizon Singularity Orchestrator"
    )

    parser.add_argument(
        "--universe",
        type=str,
        required=True,
        help="Name of the universe to initialize (e.g., 'Equities', 'Forex')"
    )

    args = parser.parse_args()

    return {
        "universe": args.universe
    }


def main():
    """
    Main application entry point.

    Execution flow:
        1. Parse command-line arguments
        2. Locate and load application configuration
        3. Resolve universe, singularity, and flight definitions
        4. Instantiate core components via factories
        5. Ignite the universe (data + preprocessing)
        6. Compress the universe into the singularity
        7. Launch the evolutionary flight loop
    """
    args = parse_args()  # Extract CLI arguments

    paths = [
        'config.user.yaml',
        'config.yaml'
    ]  # Ordered list of supported configuration files

    app_config = load_app_config(
        [p for p in paths if os.path.isfile(p)][0]
    )  # Load first existing config file

    ml_config = app_config.ml  # Extract ML configuration section

    # Set environment variable to select log_style to be discovered by base Fabric class
    # Bit hacky but we need to live with this as well
    os.environ["ML_LOG_CLASS"] = ml_config.get("log_style", "ml.space.messages.spacey")

    # Now import with right messaging style
    from ml.space.universes.factory import UniverseFactory
    from ml.space.singularities.factory import SingularityFactory
    from ml.space.flights.factory import FlightFactory

    universe_name = args.get('universe')  # Selected universe name
    universe_config = ml_config.get('universes').get(universe_name)  # Universe config block
    universe_type = universe_config.get('type')  # Universe class identifier

    singularity_config = universe_config.get('singularity')  # Singularity config block
    singularity_type = singularity_config.get('type')  # Singularity class identifier

    flight_config = universe_config.get('flight')  # Flight config block
    flight_type = flight_config.get('type')  # Flight class identifier

    singularity_config = {
        **singularity_config,
        **(flight_config.get('settings') or {})
    }  # Temporary merge of flight settings into singularity config

    universe = UniverseFactory.manifest(
        universe_type,
        universe_config
    )  # Instantiate universe

    singularity = SingularityFactory.manifest(
        singularity_type,
        singularity_config
    )  # Instantiate singularity

    flight = FlightFactory.manifest(
        flight_type,
        flight_config
    )  # Instantiate flight engine

    universe.ignite()  # Initialize data and feature space

    singularity.compress(universe)  # Train singularity on universe data

    flight.warp(singularity)  # Start evolutionary optimization loop


if __name__ == "__main__":
    main()  # Execute application