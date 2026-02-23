from ml.space.space import Universe
from ml.space.universes.milkyway import MilkyWay

from typing import Dict, Any

class UniverseFactory:

    @staticmethod
    def manifest(universe_name: str, config) -> Universe:
        """
        Factory method to create universe instances.
        """
        registry = {
            "MilkyWay": MilkyWay,
        }

        if universe_name in registry:
            return registry[universe_name](config)
        
        raise ValueError(f"🌌 [Space]: Unknown universe type '{universe_name}' requested.")