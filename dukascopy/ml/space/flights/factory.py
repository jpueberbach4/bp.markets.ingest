"""
===============================================================================
File:        factory.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Factory module for instantiating flight objects within the ML space.

    Provides a centralized factory pattern for creating flight instances, such
    as Voyager or MilleniumFalcon, based on type name and configuration.
    Supports easy extension for future flight types.

Key Capabilities:
    - Centralized flight creation
    - Configuration-driven initialization
    - Extensible registry for new flight types
===============================================================================
"""

from typing import Dict, Any

from ml.space.base import BaseFactory
from ml.space.space import Singularity
from ml.space.flights.millenniumfalcon import MilleniumFalcon


class FlightFactory(BaseFactory):
    """Factory for creating flight (singularity) instances."""

    @staticmethod
    def manifest(flight_name: str, config: Dict[str, Any]) -> Singularity:
        """Instantiate a flight based on its name and configuration.

        Args:
            flight_name (str): Name of the flight to create. Supported types
                include "Voyager" and "MilleniumFalcon".
            config (Dict[str, Any]): Configuration parameters for the flight.

        Returns:
            Singularity: An instance of the requested flight.

        Raises:
            ValueError: If the flight_name is not recognized.

        Example:
            >>> factory = FlightFactory()
            >>> voyager = factory.manifest("Voyager", config)
        """
        # Registry mapping flight names to their classes
        registry = {
            "MilleniumFalcon": MilleniumFalcon
        }

        # Create flight instance if name exists in registry
        if flight_name in registry:
            return registry[flight_name](config)

        # Extension capability
        if "." in flight_name:
            try:
                flight_class = FlightFactory._load_from_config_string(flight_name)
                return flight_class(config)
            except ImportError as e:
                raise ValueError(str(e))

        # Raise error for unknown flight types
        raise ValueError(
            f"🌌 [Flight]: Unknown flight type '{flight_name}' requested."
        )