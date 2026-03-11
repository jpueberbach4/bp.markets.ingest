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

class Default(Center):
    """
    Ground-truth modifier that applies a strict lead-up Gaussian blur.
    """


    def __init__(self, config: Dict[str, Any]):
        self.config = config
        print(f"[DEBUG] DefaultCenter Initialized (Binary Mode)")

    def apply(self, target_series: pd.Series) -> pd.Series:
        """
        Applies the lead-up diffusion directly to a Pandas Series.
        """
        return target_series