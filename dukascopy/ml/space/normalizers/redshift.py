"""
===============================================================================
File:        redshift.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of a Redshift normalizer within the ML space.

    Redshift performs Z-score normalization on tensors, transforming absolute
    values into relative coordinates using the mean and standard deviation.
    This ensures each feature has zero mean and unit variance along the
    specified dimension.

Key Capabilities:
    - Z-score normalization along a specified tensor dimension
    - Maintains input shape
    - Compatible with 2D or 3D tensors
    - Stores mean and std for potential downstream analysis
===============================================================================
"""

from ml.space.space import Normalizer
import torch


class Redshift(Normalizer):
    """
    Z-score normalizer for tensor inputs.
    
    Normalizes each feature along a given dimension using its mean and standard
    deviation: z = (x - mu) / (sigma + eps)
    """
    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary with optional keys:
                - dim (int): Dimension along which to compute mean/std (default 0)
                - eps (float): Small epsilon to avoid division by zero (default 1e-8)
        """
        super().__init__()
        self.dim: int = int(config.get('dim', 0))
        self.eps: float = float(config.get('eps', 1e-8))
        
        # Stored statistics for potential inspection or factory baseline locking
        self.means: torch.Tensor | None = None
        self.stds: torch.Tensor | None = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applies Z-score normalization along the configured dimension.
        
        Args:
            x (torch.Tensor): Input tensor to normalize.
        
        Returns:
            torch.Tensor: Normalized tensor with zero mean and unit variance.
        """
        self.print("REDSHIFT_NORMALIZE")
        mu = x.mean(dim=self.dim, keepdim=True)
        sigma = x.std(dim=self.dim, keepdim=True)
        
        # Store per-feature statistics for external use
        self.means = mu.squeeze(self.dim)
        self.stds = sigma.squeeze(self.dim)
        
        # Normalize and shift to relative cosmic coordinates
        return (x - mu) / (sigma + self.eps)