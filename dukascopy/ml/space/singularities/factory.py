"""
===============================================================================
File:        factory.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Factory module for instantiating singularity objects within the ML space.

    This module implements a centralized factory pattern for creating different
    types of evolutionary singularities, such as PulsarSingularity or 
    EventHorizonSingularity. It abstracts the construction logic, enabling 
    flexible instantiation of singularities based on configuration and type 
    name.

Key Capabilities:
    - Centralized singularity creation
    - Configuration-based initialization
    - Extensible registry for future singularities
===============================================================================
"""

from typing import Dict, Any

from ml.space.space import BaseFactory, Singularity
from ml.space.singularities.eventhorizon import EventHorizonSingularity
from ml.space.singularities.pulsar import PulsarSingularity


class SingularityFactory(BaseFactory):
    """Factory for creating singularity instances."""

    @staticmethod
    def manifest(singularity_name: str, config: Dict[str, Any]) -> Singularity:
        """Instantiate a singularity based on its name and configuration.

        Args:
            singularity_name (str): The type of singularity to create.
                Supported types include "EventHorizon" and "Pulsar".
            config (Dict[str, Any]): Configuration parameters for the singularity.

        Returns:
            Singularity: An instance of the requested singularity.

        Raises:
            ValueError: If the singularity_name is not recognized.

        Example:
            >>> factory = SingularityFactory()
            >>> pulsar = factory.manifest("Pulsar", config)
        """
        # Registry mapping names to singularity classes
        registry = {
            "EventHorizon": EventHorizonSingularity,
            "Pulsar": PulsarSingularity,
        }

        # Attempt to create singularity from registry
        if singularity_name in registry:
            return registry[singularity_name](config)
        
        # Extension capability
        if "." in singularity_name:
            try:
                singularity_class = SingularityFactory._load_from_config_string(singularity_name)
                return singularity_class(config)
            except ImportError as e:
                raise ValueError(str(e))

        # Raise error for unknown types
        raise ValueError(
            f"🌌 [Singularity]: Unknown singularity type '{singularity_name}' requested."
        )