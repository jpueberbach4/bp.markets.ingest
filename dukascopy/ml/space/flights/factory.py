from ml.space.space import Singularity
from ml.space.flights.voyager import Voyager
from ml.space.flights.millenniumfalcon import MilleniumFalcon

from typing import Dict, Any

class FlightFactory:
    """
    The Singularies Factory.
    Manifests specific comets from the cosmic void based on configuration.
    """
    @staticmethod
    def manifest(flight_name: str, config: Dict[str, Any]) -> Singularity:
        """
        Factory method to create comet instances.
        """
        registry = {
            "Voyager": Voyager,
            "MilleniumFalcon": MilleniumFalcon
        }

        if flight_name in registry:
            return registry[flight_name](config)
        
        raise ValueError(f"🌌 [Flight]: Unknown flight type '{flight_name}' requested.")