
from ml.space.space import Normalizer
from ml.space.normalizers.redshift import Redshift
from ml.space.normalizers.pulsar import Pulsar
# Import future normalizers here

class NormalizerFactory: #rename
    @staticmethod
    def manifest(normalizer_name: str, dim=0, eps=1e-8) -> Normalizer:
        """
        Factory method to create comet instances.
        """
        registry = {
            "Redshift": Redshift,
            "Pulsar": Pulsar,
        }

        if normalizer_name in registry:
            return registry[normalizer_name](dim, eps)
        
        raise ValueError(f"🌌 [Normalizer]: Unknown normalizer type '{normalizer_name}' requested.")