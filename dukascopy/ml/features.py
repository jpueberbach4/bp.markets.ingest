import numpy as np
import pandas as pd

def apply_temporal_universe(df):
    """
    Standardizes the 3x expansion (Original, Velocity, Momentum).
    """
    working_df = df.copy()
    original_cols = working_df.columns.tolist()
    
    delta_list = []
    for col in original_cols:
        # dt1: Velocity (1-bar slope)
        d1 = working_df[col].diff(1).fillna(0).rename(f"{col}_dt1")
        # dt3: Momentum (3-bar trend)
        d3 = working_df[col].diff(3).fillna(0).rename(f"{col}_dt3")
        delta_list.extend([d1, d3])
    
    full_df = pd.concat([working_df] + delta_list, axis=1)
    full_df = full_df.replace([np.inf, -np.inf], 0).fillna(0)
    return full_df