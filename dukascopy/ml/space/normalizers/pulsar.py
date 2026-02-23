from ml.space.space import Normalizer
import torch

class Pulsar(Normalizer):
    """
    A Min-Max Scaler.
    Normalizes data between 0 and 1, like the periodic 
    pulses of a neutron star.
    """
    def __init__(self, config):
        super().__init__()
        self.dim = config.get('dim', 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_min = x.min(dim=self.dim, keepdim=True)[0]
        x_max = x.max(dim=self.dim, keepdim=True)[0]
        return (x - x_min) / (x_max - x_min + 1e-8)