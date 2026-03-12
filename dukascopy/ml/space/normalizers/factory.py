"""
===============================================================================
File:        factory.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Factory module for instantiating normalizer objects within the ML space.

    Provides a centralized factory pattern for creating normalizer instances,
    such as Redshift, Pulsar, or Kinematics, based on type name and configuration.
    Supports easy extension to include future normalizers.

Key Capabilities:
    - Centralized normalizer creation
    - Configuration-driven initialization
    - Extensible registry for new normalizer types
===============================================================================
"""

from typing import Any, Dict

from ml.space.base import BaseFactory
from ml.space.space import Normalizer
from ml.space.normalizers.redshift import Redshift
from ml.space.normalizers.redshift2 import Redshift2
from ml.space.normalizers.pulsar import Pulsar
from ml.space.normalizers.kinematics import Kinematics


class NormalizerFactory(BaseFactory):
    """Factory for creating normalizer instances."""

    @staticmethod
    def manifest(normalizer_name: str, config: Dict[str, Any]) -> Normalizer:
        """Instantiate a normalizer based on its name and configuration.

        Args:
            normalizer_name (str): Name of the normalizer to create. Supported
                types include "Redshift", "Pulsar", and "Kinematics".
            config (Dict[str, Any]): Configuration parameters for the normalizer.

        Returns:
            Normalizer: An instance of the requested normalizer.

        Raises:
            ValueError: If the normalizer_name is not recognized.

        Example:
            >>> factory = NormalizerFactory()
            >>> redshift_norm = factory.manifest("Redshift", config)
        """
        # Registry mapping normalizer names to their classes
        registry = {
            "Redshift": Redshift,
            "Redshift2": Redshift2,
            "Pulsar": Pulsar,
            "Kinematics": Kinematics,
        }

        # Create normalizer instance if name exists in registry
        if normalizer_name in registry:
            return registry[normalizer_name](config)
        
        # Extension capability
        if "." in normalizer_name:
            try:
                normalizer_class = NormalizerFactory._load_from_config_string(normalizer_name)
                return normalizer_class(config)
            except ImportError as e:
                raise ValueError(str(e))

        # Raise error for unknown normalizer types
        raise ValueError(
            f"🌌 [Normalizer]: Unknown normalizer type '{normalizer_name}' requested."
        )