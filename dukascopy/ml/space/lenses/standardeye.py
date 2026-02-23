
from ml.space.space import Lens
import torch
import torch.nn as nn

class StandardEye(Lens):
    """Standard Binary Cross Entropy for balanced observation."""
    def __init__(self):
        super().__init__()
        self.loss = nn.BCEWithLogitsLoss()

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.loss(inputs, targets)