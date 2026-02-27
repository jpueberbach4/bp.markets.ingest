"""
===============================================================================
File:        standardeye.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of a StandardEye lens within the ML space.

    StandardEye applies binary cross-entropy loss to model predictions, serving
    as a baseline lens for balanced datasets. Integrates seamlessly with PyTorch
    training loops and can be used interchangeably with other Lens instruments
    such as GravitationalLens.

Key Capabilities:
    - Binary cross-entropy computation for balanced observations
    - Simple, reusable lens for model loss evaluation
    - Compatible with PyTorch forward/backward operations
===============================================================================
"""

from ml.space.space import Lens
import torch
import torch.nn as nn


class StandardEye(Lens):
    """Binary Cross-Entropy lens for balanced event observation."""

    def __init__(self):
        """Initializes the StandardEye lens with BCE loss."""
        super().__init__()
        self.loss = nn.BCEWithLogitsLoss()

        self.print("STANDARDEYE_INIT")

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Computes binary cross-entropy loss between predictions and targets.

        Args:
            inputs (torch.Tensor): Model outputs (logits).
            targets (torch.Tensor): Ground-truth labels (0 or 1).

        Returns:
            torch.Tensor: Computed BCE loss.
        """
        return self.loss(inputs, targets)