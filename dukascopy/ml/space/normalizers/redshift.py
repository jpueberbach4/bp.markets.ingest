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
        
        # State tracking for Factory Spec baseline locking
        self.means = None
        self.stds = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applies Redshift to the incoming tensor.
        """
        print(f"🌌 [Space]: Establishing physics. Z-Score.")
        mu = x.mean(dim=self.dim, keepdim=True)
        sigma = x.std(dim=self.dim, keepdim=True)
        
        # Lock the global physics parameters into the class state.
        # Squeezing removes the target dimension to create a flat 1D tensor 
        # mapping directly to the feature indices.
        self.means = mu.squeeze(self.dim)
        self.stds = sigma.squeeze(self.dim)
        
        # Shift the matter to the center of the universe
        return (x - mu) / (sigma + self.eps)