"""
===============================================================================
File:        factory.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Factory module for instantiating universe objects within the ML space.

    This module provides a centralized factory pattern for creating different
    universe instances, such as MilkyWay. It abstracts construction logic and
    allows flexible instantiation based on type name and configuration.

Key Capabilities:
    - Centralized universe creation
    - Configuration-driven initialization
    - Extensible registry for future universes
===============================================================================
"""

from typing import Dict, Any

from ml.space.space import Universe
from ml.space.universes.milkyway import MilkyWay


class UniverseFactory:
    """Factory for creating universe instances."""

    @staticmethod
    def manifest(universe_name: str, config: Dict[str, Any]) -> Universe:
        """Instantiate a universe based on its name and configuration.

        Args:
            universe_name (str): Name of the universe to create. Supported types include "MilkyWay".
            config (Dict[str, Any]): Configuration parameters for the universe.

        Returns:
            Universe: An instance of the requested universe.

        Raises:
            ValueError: If the universe_name is not recognized.

        Example:
            >>> factory = UniverseFactory()
            >>> milkyway = factory.manifest("MilkyWay", config)
        """
        # Registry mapping universe names to classes
        registry = {
            "MilkyWay": MilkyWay,
        }

        # Create universe if name exists in registry
        if universe_name in registry:
            return registry[universe_name](config)

        # Raise error for unknown universe types
        raise ValueError(
            f"🌌 [Space]: Unknown universe type '{universe_name}' requested."
        )