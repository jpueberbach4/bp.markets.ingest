
from ml.space.space import Lens
import torch
import torch.nn as nn

class GravitationalLens(Lens):
    """Focal Loss implementation for rare event magnification."""
    def __init__(self, alpha=0.99, gamma=3.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        import torch.nn.functional as F
        bce_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        probs = torch.sigmoid(inputs)
        pt = torch.where(targets == 1.0, probs, 1.0 - probs)
        return (self.alpha * (1.0 - pt)**self.gamma * bce_loss).mean()