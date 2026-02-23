from ml.space.space import Comet
from ml.space.comets.halebopp import HaleBopp
# Import future comets here (e.g., from ml.space.comets.encke import Encke)

class CometFactory:
    """
    The Comet Factory.
    Manifests specific comets from the cosmic void based on configuration.
    """
    @staticmethod
    def manifest(comet_name: str) -> Comet:
        """
        Factory method to create comet instances.
        """
        registry = {
            "HaleBopp": HaleBopp,
            # "Encke": Encke,  # Example for future DB or Telemetry comets
        }

        if comet_name in registry:
            return registry[comet_name]()
        
        raise ValueError(f"🌌 [OortCloud]: Unknown comet type '{comet_name}' requested.")