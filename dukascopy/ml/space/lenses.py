
from ml.space.space import Lens
import torch
import torch.nn as nn

class Spectrograph:
    """
    The Base Instrument.
    Manages the selection and application of different Lenses
    to analyze the model's performance.
    """
    def __init__(self, mode: str, **kwargs):
        self.mode = mode
        self.lens = self._ignite_lens(mode, **kwargs)
        print(f"🔬 [Spectrograph]: Instrument active using {self.lens.__class__.__name__} configuration.")

    def _ignite_lens(self, mode: str, **kwargs) -> Lens:
        """
        Factory method to manifest the requested lens.
        """
        if mode == "focal":
            return GravitationalLens(**kwargs)
        elif mode == "bce":
            return StandardEye(**kwargs)
        else:
            raise ValueError(f"❌ [Spectrograph Error]: Unknown lens mode: {mode}")

    def analyze(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Passes the data through the lens to calculate loss.
        """
        return self.lens(inputs, targets)
    
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

class StandardEye(Lens):
    """Standard Binary Cross Entropy for balanced observation."""
    def __init__(self):
        super().__init__()
        self.loss = nn.BCEWithLogitsLoss()

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.loss(inputs, targets)