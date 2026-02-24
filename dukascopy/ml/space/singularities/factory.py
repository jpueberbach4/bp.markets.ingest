from ml.space.space import Singularity
from ml.space.singularities.eventhorizon import EventHorizonSingularity
from ml.space.singularities.pulsar import PulsarSingularity

from typing import Dict, Any

class SingularityFactory:
    """
    The Singularies Factory.
    Manifests specific comets from the cosmic void based on configuration.
    """
    @staticmethod
    def manifest(singularity_name: str, config: Dict[str, Any]) -> Singularity:
        """
        Factory method to create comet instances.
        """
        registry = {
            "EventHorizon": EventHorizonSingularity,
            "Pulsar": PulsarSingularity,
        }

        if singularity_name in registry:
            return registry[singularity_name](config)
        
        raise ValueError(f"🌌 [Constellation]: Unknown singularity type '{singularity_name}' requested.")