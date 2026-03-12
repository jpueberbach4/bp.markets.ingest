"""
===============================================================================
File:        gravitational.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of a GravitationalLens for rare-event magnification within
    the ML space. This lens applies a focal loss to emphasize rare positive
    events during training, improving model sensitivity to imbalanced signals.

Key Capabilities:
    - Focal loss computation for binary classification
    - Adjustable alpha and gamma parameters for weighting
    - Integrates seamlessly with PyTorch training loops
===============================================================================
"""

import torch
import torch.nn.functional as F
from ml.space.space import Lens


class GravitationalLens(Lens):
    """Focal Loss for rare-event magnification in time-series or binary signals."""

    def __init__(self, config):
        """Initialize GravitationalLens with weighting parameters.

        Args:
            alpha (float): Balancing factor for positive class weight (default 0.99).
            gamma (float): Focusing parameter to reduce loss for well-classified examples (default 3.0).
        """
        super().__init__()
        self.config = config
        self.alpha = float(self.config.get("alpha"))
        self.gamma = float(self.config.get("gamma"))

        self.print("GRAVITATIONALLENS_INIT")

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute the focal loss for binary classification.

        Args:
            inputs (torch.Tensor): Raw logits output from the model, shape (N, *).
            targets (torch.Tensor): Binary ground truth tensor, same shape as inputs.

        Returns:
            torch.Tensor: Scalar focal loss value.
        """
        # Compute standard binary cross-entropy without reduction
        bce_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction="none")

        # Convert logits to probabilities
        probs = torch.sigmoid(inputs)

        # pt: probability assigned to the true class for each example
        pt = torch.where(targets == 1.0, probs, 1.0 - probs)

        # alpha_t: dynamically apply alpha to the positive class and (1 - alpha) to the negative class
        alpha_t = torch.where(targets == 1.0, self.alpha, 1.0 - self.alpha)

        # Apply focal loss weighting with corrected alpha balancing
        focal_loss = alpha_t * (1.0 - pt) ** self.gamma * bce_loss

        # Return mean loss over the batch
        return focal_loss.mean()