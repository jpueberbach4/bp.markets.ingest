import pytz
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

def resample_post_process_merge(df: pd.DataFrame, ident:str, step, config) -> pd.DataFrame:
    offset = step.offset
    for ends_with in step.ends_with:
        positions = np.where(df.index.str.endswith(ends_with))[0]

        for pos in positions:
            # Ensure there is a row before the selects to merge into
            if pos > 0:
                anchor_pos = pos + offset
                # Make sure the anchor_pos is actually existing
                if 0 <= anchor_pos < len(df):

                    # Get index of select and the anchor
                    select_idx = df.index[pos]
                    anchor_idx = df.index[anchor_pos]

                    # Perform the logic, determine high, low, close and sum volume
                    df.at[anchor_idx, 'high'] = max(
                        df.at[anchor_idx, 'high'],
                        df.at[select_idx, 'high'],
                    )
                    df.at[anchor_idx, 'low'] = min(
                        df.at[anchor_idx, 'low'],
                        df.at[select_idx, 'low'],
                    )
                    df.at[anchor_idx, 'close'] = df.at[select_idx, 'close']
                    df.at[anchor_idx, 'volume'] += df.at[select_idx, 'volume']
                else:
                    # Error in offset definition, fail!
                    raise PostProcessingError(f"Post-processing error for {self.symbol} at timeframe {self.ident}")


        # Drop all selected source columns
        df = df[~df.index.str.endswith(ends_with)]

    # Return the data frame
    return df