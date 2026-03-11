import numpy as np
import pandas as pd
from typing import Dict, Any
from ml.space.space import Center

class LinearLeft(Center):
    """
    Applies a steady linear ramp lead-up to the event.
    Example (window=4): [0.25, 0.50, 0.75, 1.0, 0, 0]
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.window = int(self.config.get("window", 4))
        
        self.kernel = np.linspace(0, 1, self.window + 1)[1:]
        
        print(f"[DEBUG] LinearCenter Initialized: {self.window} candle ramp.")

    def apply(self, target_series: pd.Series) -> pd.Series:
        target_array = target_series.values.astype(np.float32)
        blurred_full = np.convolve(target_array, self.kernel, mode='full')
        aligned_array = blurred_full[len(self.kernel) - 1:]
        
        return pd.Series(np.clip(aligned_array, 0.0, 1.0), 
                         index=target_series.index, name=target_series.name)