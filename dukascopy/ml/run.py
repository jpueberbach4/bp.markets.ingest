from util.config import load_app_config
from typing import Dict, Any
from ml.space.universes.factory import UniverseFactory
from ml.space.singularities.factory import SingularityFactory
from ml.space.flights.factory import FlightFactory
import os
import argparse

def parse_args() -> Dict[str, Any]:
    """
    Parses command line arguments and identifies the available configuration file.
    
    Returns:
        Dict[str, Any]: A dictionary containing the universe name and the 
                        path to the detected configuration file.
    """
    parser = argparse.ArgumentParser(description="Event Horizon Singularity Orchestrator")
    
    # --universe name
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
    args = parse_args()

    paths = [
        'config.user.yaml',
        'config.yaml'
    ]

    app_config = load_app_config([p for p in paths if os.path.isfile(p)][0])
    ml_config = app_config.ml

    # initialize universe
    universe_name = args.get('universe')
    universe_config = ml_config.get('universes').get(universe_name)
    universe_type = universe_config.get('type')

    singularity_config = universe_config.get('singularity')
    singularity_type = singularity_config.get('type')

    flight_config = universe_config.get('flight')
    flight_type = flight_config.get('type')

    # instantiate universe
    universe = UniverseFactory.manifest(universe_type, universe_config)

    # instantiate singularity
    singularity = SingularityFactory.manifest(singularity_type, singularity_config)

    # instantiate flight
    flight = FlightFactory.manifest(flight_type, flight_config)

    # ignite the universe
    universe.ignite()

    # compress the universe into the singularity
    singularity.compress(universe)

    # make the bigbang happen
    universe.bigbang()

    # start main loop
    flight.warp(singularity)


if __name__ == "__main__":
    main()