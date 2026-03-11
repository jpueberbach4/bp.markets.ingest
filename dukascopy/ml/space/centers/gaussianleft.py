"""
===============================================================================
File:        gaussian_center.py
Author:      JP Ueberbach
Created:     2026-03-11

Description:
    Applies an Anti-Causal (Left-Sided) Half-Gaussian diffusion to binary targets.
    
    This class transforms hard binary labels into smoothed probability 
    distributions strictly for the *lead-up* to an event. 
    
    Lookahead bias is mathematically eliminated: the signal drops to 0.0 
    immediately after the event peak. This trains the model to recognize 
    the approach of a market extreme without leaking future state.
===============================================================================
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

from ml.space.space import Center

class GaussianLeft(Center):
    """
    Ground-truth modifier that applies a strict lead-up Gaussian blur.
    """


    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.gamma = float(self.config.get("gamma", 5.0))
        
        # 1. Generate the Right-Sided Decay Curve
        tail_length = int(self.gamma * 4)
        x = np.arange(tail_length + 1)
        decay_curve = np.exp(-0.5 * (x / self.gamma)**2)
        
        # 2. Reverse it to create an Anti-Causal Kernel
        self.kernel = decay_curve[::-1]

        print(f"[DEBUG] GaussianCenter Initialized (Anti-Causal Series Mode)")
        print(f"[DEBUG] Lead-up Window : {tail_length} candles")

    def apply(self, target_series: pd.Series) -> pd.Series:
        """
        Applies the lead-up diffusion directly to a Pandas Series.
        """
        target_array = target_series.values.astype(np.float32)

        # Apply the convolution
        blurred_full = np.convolve(target_array, self.kernel, mode='full')
        
        # Slice the overhang perfectly to align the 1.0 peak
        aligned_array = blurred_full[len(self.kernel) - 1:]
        
        # Clamp values to 1.0
        normalized_array = np.clip(aligned_array, 0.0, 1.0)

        # Return as a new Series, preserving the original index and name
        return pd.Series(
            normalized_array, 
            index=target_series.index, 
            name=target_series.name
        )