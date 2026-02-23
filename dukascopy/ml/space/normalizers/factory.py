
from ml.space.space import Normalizer
from ml.space.normalizers.redshift import Redshift
from ml.space.normalizers.pulsar import Pulsar
from ml.space.normalizers.kinematics import Kinematics
# Import future normalizers here

class NormalizerFactory: #rename
    @staticmethod
    def manifest(normalizer_name: str, config) -> Normalizer:
        """
        Factory method to create comet instances.
        """
        registry = {
            "Redshift": Redshift,
            "Pulsar": Pulsar,
            "Kinematics": Kinematics,
        }

        if normalizer_name in registry:
            return registry[normalizer_name](config)
        
        raise ValueError(f"🌌 [Normalizer]: Unknown normalizer type '{normalizer_name}' requested.")