import numpy as np
import pandas as pd
from pathlib import Path

# Match your binary.py definition
DTYPE = np.dtype([
    ('ts', '<u8'),           # Timestamp uint64
    ('ohlcv', '<f8', (5,)),  # OHLCV float64
    ('padding', '<u8', (2,)) # Padding
])

def dump_binary_file(filepath: str, num_records: int = 10):
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        return

    # Map the file and read records
    data = np.fromfile(path, dtype=DTYPE)
    
    # Convert to DataFrame for readable output
    df = pd.DataFrame(
        data['ohlcv'],
        columns=['open', 'high', 'low', 'close', 'volume'],
        index=pd.to_datetime(data['ts'], unit='ms')
    )
    
    print(f"--- Top {num_records} records of {path.name} ---")
    print(df.head(num_records))
    print(f"\n--- Bottom {num_records} records of {path.name} ---")
    print(df.tail(num_records))
    print(f"\nTotal Records: {len(data)}")

# Usage
dump_binary_file("data/aggregate/1m/EUR-USD.bin")


#dump_binary_file("data/resample/5m/EUR-USD.bin")