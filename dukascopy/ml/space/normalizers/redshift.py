from ml.space.space import Normalizer
import torch

class Redshift(Normalizer):
    """
    A Z-Score Normalizer.
    Transforms absolute matter into relative cosmic coordinates 
    using the mean and standard deviation.
    
    Formula: $z = \frac{x - \mu}{\sigma}$
    """
    def __init__(self, config):
        super().__init__()
        self.dim = int(config.get('dim', 0))
        self.eps = float(config.get('eps', 1e-8)) # Prevents division by zero in a vacuum

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applies Redshift to the incoming tensor.
        """
        print(f"🌌 [Space]: Establishing physics. Z-Score.")
        mu = x.mean(dim=self.dim, keepdim=True)
        sigma = x.std(dim=self.dim, keepdim=True)
        
        # Shift the matter to the center of the universe
        return (x - mu) / (sigma + self.eps)

