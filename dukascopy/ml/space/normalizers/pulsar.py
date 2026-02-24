"""
===============================================================================
File:        pulsar.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of a Pulsar normalizer within the ML space.

    Pulsar acts as a Min-Max scaler for selected tensor dimensions, mapping
    values into the [0, 1] range. Named after the periodic pulses of a
    neutron star, it standardizes data to maintain relative amplitude
    while bounding extremes.

Key Capabilities:
    - Min-Max normalization along a specified dimension
    - Maintains shape of input tensor
    - Compatible with 2D or 3D input tensors
    - Device-aware and differentiable with PyTorch autograd
===============================================================================
"""

from ml.space.space import Normalizer
import torch


class Pulsar(Normalizer):
    """
    Min-Max scaler for tensor inputs.
    
    Normalizes values to the range [0, 1] along a given dimension.
    """
    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary with optional keys:
                - dim (int): Dimension along which to compute min/max (default 0)
        """
        super().__init__()
        self.dim: int = config.get('dim', 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applies min-max normalization to the input tensor.
        
        Args:
            x (torch.Tensor): Input tensor to normalize.
        
        Returns:
            torch.Tensor: Normalized tensor with values in [0, 1].
        """
        x_min = x.min(dim=self.dim, keepdim=True)[0]
        x_max = x.max(dim=self.dim, keepdim=True)[0]
        return (x - x_min) / (x_max - x_min + 1e-8)