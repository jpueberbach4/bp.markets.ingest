"""
===============================================================================
File:        factory.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Factory module for instantiating lens objects within the ML space.

    This module implements a centralized factory pattern for creating concrete
    `Lens` instances (e.g., `GravitationalLens`, `StandardEye`) based on a string
    identifier and a configuration dictionary. It enables configuration-driven
    initialization and provides a clean extension point for introducing new
    lens types without modifying existing client code.

Key Capabilities:
    - Centralized lens creation
    - Configuration-driven initialization
    - Extensible registry and dynamic loading support
===============================================================================
"""

from typing import Dict, Any

from ml.space.space import BaseFactory
from ml.space.space import Lens
from ml.space.lenses.gravitational import GravitationalLens
from ml.space.lenses.standardeye import StandardEye


class LensFactory(BaseFactory):
    """Factory for creating `Lens` instances.

    This factory resolves a lens name to its concrete implementation and
    instantiates it using the provided configuration. It supports both a
    static registry for known lenses and a dynamic import mechanism for
    externally defined or configurable lens implementations.
    """

    @staticmethod
    def manifest(lens_name: str, config: Dict[str, Any]) -> Lens:
        """Instantiate a lens based on its name and configuration.

        Args:
            lens_name (str): Name of the lens to create. Supported built-in
                types include `"Gravitational"` and `"StandardEye"`. Fully
                qualified import paths may also be provided for dynamically
                loaded lenses.
            config (Dict[str, Any]): Configuration parameters used to
                initialize the lens instance.

        Returns:
            Lens: An instantiated lens corresponding to the requested name.

        Raises:
            ValueError: If the lens name is not recognized or cannot be
                dynamically imported.

        Example:
            >>> lens = LensFactory.manifest("Gravitational", config)
        """
        # Registry mapping lens names to their classes
        registry = {
            "Gravitational": GravitationalLens,
            "StandardEye": StandardEye
        }

        # Create lens instance if name exists in registry
        if lens_name in registry:
            return registry[lens_name](config)

        # Extension capability via dynamic import
        if "." in lens_name:
            try:
                flight_class = LensFactory._load_from_config_string(lens_name)
                return flight_class(config)
            except ImportError as e:
                raise ValueError(str(e))

        # Raise error for unknown lens types
        raise ValueError(
            f"🌌 [Lens]: Unknown lens type '{lens_name}' requested."
        )