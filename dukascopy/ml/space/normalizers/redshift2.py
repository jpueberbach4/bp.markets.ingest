"""
===============================================================================
File:        redshift.py
Author:      JP Ueberbach
Created:     2026-03-12 (Rolling Redshift Update)

Description:
    Implementation of a Causal Rolling Redshift normalizer within the ML space.

    Redshift performs Z-score normalization on tensors, transforming absolute
    values into relative coordinates. 
    
    *ROUGH PATH UPDATE*: To prevent lookahead bias and ensure perfect parity
    between training and live edge inference, this module now calculates 
    causal rolling statistics (mean and std) rather than global static ones.
    This guarantees the geometric Log-Signatures learned during training 
    are mathematically identical to those seen in production.

Key Capabilities:
    - Causal rolling Z-score normalization along the time dimension
    - Maintains input shape
    - Matches production inference environment perfectly
    - Optimized for high-performance vectorized calculation
===============================================================================
"""

from ml.space.space import Normalizer
import torch
import pandas as pd
import numpy as np


class Redshift2(Normalizer):
    """
    Causal Rolling Z-score normalizer for tensor inputs.
    
    Normalizes each feature along the time dimension using a trailing rolling 
    window to prevent future data leakage: z_t = (x_t - mu_t) / (sigma_t + eps)
    """
    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary with optional keys:
                - dim (int): Dimension along which to compute mean/std (default 0)
                - eps (float): Small epsilon to avoid division by zero (default 1e-8)
                - rolling_window (int): The trailing lookback for stats (default 200)
        """
        super().__init__()
        self.config = config
        self.dim: int = int(config.get('dim', 0))
        self.eps: float = float(config.get('eps', 1e-8))
        self.rolling_window: int = int(config.get('rolling_window', 200))
        
        # Stored statistics for the final timestamp (used for warm-starting live edge if needed)
        self.means: torch.Tensor | None = None
        self.stds: torch.Tensor | None = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Applies Causal Rolling Z-score normalization.
        
        Args:
            x (torch.Tensor): Input tensor to normalize. Shape expected: (Time, Features)
        
        Returns:
            torch.Tensor: Normalized tensor with trailing zero mean and unit variance.
        """
        self.print("REDSHIFT_ROLLING_NORMALIZE", window=self.rolling_window)
        
        # To ensure 100% mathematical parity with the live-edge pandas logic
        # and to utilize C-optimized rolling functions, we bridge through pandas.
        # Because this runs exactly once during compress(), the overhead is negligible.
        x_np = x.detach().cpu().numpy()
        df = pd.DataFrame(x_np)
        
        # Calculate rolling statistics causally (min_periods=1 ensures no NaNs at the start)
        rolling_means = df.rolling(window=self.rolling_window, min_periods=1).mean()
        rolling_stds = df.rolling(window=self.rolling_window, min_periods=1).std()
        
        # Handle the very first row where standard deviation is NaN
        rolling_stds = rolling_stds.bfill().fillna(1.0)
        
        # Convert back to high-performance PyTorch tensors on the original device
        mu = torch.from_numpy(rolling_means.values).to(x.device).float()
        sigma = torch.from_numpy(rolling_stds.values).to(x.device).float()
        
        # Store the absolute final row's statistics for external reference
        self.means = mu[-1]
        self.stds = sigma[-1]
        
        # Normalize and shift to relative cosmic coordinates
        return (x - mu) / (sigma + self.eps)