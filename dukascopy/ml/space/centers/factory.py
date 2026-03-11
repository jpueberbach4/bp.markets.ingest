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

from typing import Dict, Any
from ml.space.base import BaseFactory
from ml.space.space import Center
from ml.space.centers.gaussianleft import GaussianLeft
from ml.space.centers.default import Default



class CenterFactory(BaseFactory):
    """Factory for creating center instances."""

    @staticmethod
    def manifest(center_name: str, config: Dict[str, Any]) -> Center:
        """Instantiate a center based on its name.

        Args:
            center_name (str): Name of the center to create. Supported types
                currently include "GaussianLeft".

        Returns:
            Comet: An instance of the requested center.

        Raises:
            ValueError: If the center_name is not recognized.

        Example:
            >>> factory = CenterFactory()
            >>> gaussian_left = factory.manifest("GaussianLeft")
        """
        # Registry mapping center names to their classes
        registry = {
            "Default": Default,
            "GaussianLeft": GaussianLeft,
        }

        # Create center instance if name exists in registry
        if center_name in registry:
            return registry[center_name](config)
        
        # Extension capability
        if "." in center_name:
            try:
                center_class = CenterFactory._load_from_config_string(center_name)
                return center_class(config)
            except ImportError as e:
                raise ValueError(str(e))

        # Raise error for unknown center types
        raise ValueError(
            f"🌌 [Center]: Unknown center type '{center_name}' requested."
        )