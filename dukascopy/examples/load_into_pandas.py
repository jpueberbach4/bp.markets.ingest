import pandas as pd
"""
This script is an example on how to query data in various ways

Make sure you do a

export PYTHONPATH=$PYTHONPATH:$(pwd)

from the root url (the directory where config.yaml exists)

(I will eliminate the need for this soon)

then

python3 examples/load_into_pandas.py

"""
import time
# ---------------------------------------------------------------------------------------------------------
# First example, loading from HTTP API. Using CSV mode
# ---------------------------------------------------------------------------------------------------------

url = ("http://localhost:8000/ohlcv/1.1/select/EUR-USD,1m["
      "adx(14):atr(14):ema(20):bbands(20,2.0):macd(12,26,9)"
      "]/after/2025-11-17+19:00:00/output/CSV?limit=10000&order=asc")

start = time.perf_counter()
df = pd.read_csv(url)
print(df.tail())
print(f"time-passed: {(time.perf_counter()-start)*1000}\n\n")

# ---------------------------------------------------------------------------------------------------------
# Second example, loading from HTTP API. Using JSON mode - subformat 3
# ---------------------------------------------------------------------------------------------------------

import requests

url = ("http://localhost:8000/ohlcv/1.1/select/EUR-USD,1m["
      "adx(14):atr(14):ema(20):bbands(20,2.0):macd(12,26,9)"
      "]/after/2025-11-17+19:00:00/output/JSON?limit=10000&order=asc&subformat=3")

# Execute the Request
start = time.perf_counter()
response = requests.get(url)
response.raise_for_status()  # Check for HTTP errors (404, 500, etc.)
data = response.json()

df = pd.DataFrame(data['result'])

# Convert 'time' (epoch ms) to a readable datetime format
df['time'] = pd.to_datetime(df['time'], unit='ms')

print(df.tail())
print(f"time-passed: {(time.perf_counter()-start)*1000}\n\n")


# ---------------------------------------------------------------------------------------------------------
# Third example, the direct API approach
# ---------------------------------------------------------------------------------------------------------

from util.api import get_data
from datetime import datetime, timezone

# Define the indicators
indicators = ['adx_14', 'atr_14', 'ema_20', 'bbands_20_2.0', 'macd_12_26_9']


start = time.perf_counter()

# Convert the timestring
timestamp_str = "2025-11-17+19:00:00"
dt = datetime.strptime(timestamp_str, "%Y-%m-%d+%H:%M:%S")
after_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

start = time.perf_counter()
df = get_data(symbol="EUR-USD", timeframe="1m", indicators=indicators, after_ms=after_ms, limit=100, order="asc" )
print(f"100 records, time-passed: {(time.perf_counter()-start)*1000} (this is with one-time plugin load)  + 5 indicators\n\n")

start = time.perf_counter()
df = get_data(symbol="EUR-USD", timeframe="1m", indicators=indicators, after_ms=after_ms, limit=1000, order="asc" )
print(f"1.000 records, time-passed: {(time.perf_counter()-start)*1000} + 5 indicators\n\n")


start = time.perf_counter()
df = get_data(symbol="EUR-USD", timeframe="1m", indicators=indicators, after_ms=after_ms, limit=10000, order="asc" )
print(f"10.000 records, time-passed: {(time.perf_counter()-start)*1000} + 5 indicators\n\n")


print(df.tail())
