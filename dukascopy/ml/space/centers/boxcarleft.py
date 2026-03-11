import numpy as np
import pandas as pd
from typing import Dict, Any
from ml.space.space import Center

class BoxcarLeft(Center):
    """
    Applies a binary 'Kill Zone' window. 
    Every candle within the window leading to the event is 1.0.
    Example (window=4): [1.0, 1.0, 1.0, 1.0, 0, 0]
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.window = int(self.config.get("window", 4))
        
        self.kernel = np.ones(self.window + 1)
        
        print(f"[DEBUG] BoxcarCenter Initialized: {self.window} candle Kill Zone.")

    def apply(self, target_series: pd.Series) -> pd.Series:
        target_array = target_series.values.astype(np.float32)
        blurred_full = np.convolve(target_array, self.kernel, mode='full')
        aligned_array = blurred_full[len(self.kernel) - 1:]
        return pd.Series((aligned_array > 0).astype(np.float32), 
                         index=target_series.index, name=target_series.name)