"""
===============================================================================
File:        factory.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Factory module for instantiating comet objects within the ML space.

    Provides a centralized factory pattern for creating comet instances, such
    as HaleBopp, based on type name and configuration. Supports easy extension
    to include future comet types.

Key Capabilities:
    - Centralized comet creation
    - Extensible registry for new comet types
===============================================================================
"""

from ml.space.base import BaseFactory
from ml.space.space import Comet
from ml.space.comets.halebopp import HaleBopp


class CometFactory(BaseFactory):
    """Factory for creating comet instances."""

    @staticmethod
    def manifest(comet_name: str) -> Comet:
        """Instantiate a comet based on its name.

        Args:
            comet_name (str): Name of the comet to create. Supported types
                currently include "HaleBopp".

        Returns:
            Comet: An instance of the requested comet.

        Raises:
            ValueError: If the comet_name is not recognized.

        Example:
            >>> factory = CometFactory()
            >>> halebopp = factory.manifest("HaleBopp")
        """
        # Registry mapping comet names to their classes
        registry = {
            "HaleBopp": HaleBopp,
        }

        # Create comet instance if name exists in registry
        if comet_name in registry:
            return registry[comet_name]()
        
        # Extension capability
        if "." in comet_name:
            try:
                comet_class = CometFactory._load_from_config_string(comet_name)
                return comet_class()
            except ImportError as e:
                raise ValueError(str(e))

        # Raise error for unknown comet types
        raise ValueError(
            f"🌌 [Comet]: Unknown comet type '{comet_name}' requested."
        )