## Pipeline Configuration (v0.3 and above)

**THIS SECTION NEEDS AN OVERHAUL. USE THE [EXISTING CONFIG](../config) AS DOCUMENTATION. PLENTY OF EXAMPLES IN THERE.**

[Example for Dukascopy](../config.dukascopy-mt4.yaml)

A default ```config.yaml``` is included with the project. This file controls the behavior of the aggregate, download, transform and resample engine. You can now define custom timeframes and apply per-symbol overrides as needed.

To override the default configuration, create a user-specific copy:

```sh
cp config.yaml config.user.yaml
```

❗**IMPORTANT** If you backtest against MT4, or use this for MT4, it makes sense to configure ```time_shift_ms```. When you already have a dataset and change ```time_shift_ms```, you will need to do a rebuild from scratch using ```./rebuild-full.sh```. When you only change timeframes, a ```./rebuild-weekly.sh``` is sufficient.

The configuration file is straightforward and mostly self-explanatory. Adjust values as needed to suit your data and workflow.

**Note:** If you need to add custom configuration files that should be included alongside the main config, create a config.user directory. This directory is explicitly excluded from Git, so your local changes won’t be tracked or cause noise in version control.

```yaml
transform:
  time_shift_ms: 0                    # How many milliseconds should we shift (0=UTC, 7200000=GMT+2 (eg MT4 Dukascopy) ) (!IMPORTANT!)
  round_decimals: 8                   # Number of decimals to round OHLCV to
  paths:
    data: data/transform/1m           # Output directory for transform
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
  timezones:
    includes:
    - config.user/my/custom/config/files/*.yaml
```

Full configuration example with explanatory details:

```yaml
## Below you will find the configuration for the aggregate.py script. 
aggregate:
  paths:
    data: data/aggregate/1m           # Output path for aggregate
    source: data/transform/1m         # Input path for aggregate
## Below you will find the configuration for the builder script
builder:
  paths:
    data: data                        # Input path for builder
    temp: data/temp/builder           # Temporary path for builder
## Below you will find the configuration for the download.py script. 
download:
  max_retries: 3                      # Number of retries before downloader raises
  backoff_factor: 2                   # Exponential backoff factor (wait time)
  timeout: 10                         # Request timeout
  rate_limit_rps: 1                   # Protect end-point (number of cores * rps = requests/second)
  paths:
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
## Below you will find the configuration for the transform.py script. 
transform:
  time_shift_ms: 0                    # How many milliseconds should we shift (0=UTC, 7200000=GMT+2 (eg MT4 Dukascopy) ) (!IMPORTANT!)
  round_decimals: 8                   # Number of decimals to round OHLCV to
  paths:
    data: data/transform/1m           # Output directory for transform
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
  timezones:
    America/New_York:                 # The MT4 Server switches between GMT+2/GMT+3 based on DST change of this timezone
      offset_to_shift_map:            # Defines a map to shift based on offset minutes
        -240: 10800000                # UTC-4 (US DST) -> GMT+3 shift
        -300: 7200000                 # UTC-5 (US Standard) -> GMT+2 shift
      symbols:                        # Basically you add any symbol you are using here.
      - SYMBOL1                       # Investigation about Crypto is ongoing. 
      - SYMBOL2
## Below you will find the configuration for the resample.py script. 
resample:
  round_decimals: 8                    # Number of decimals to round OHLCV to
  batch_size: 250000                   # Maximum number of lines to read per batch
  paths:
    data: data/resample                # Output directory for resampled timeframes
  timeframes:
    1m:
      source: "data/aggregate/1m"      # No rule, no resample, source defines output path for this timeframe
    5m:
      rule: "5T"                       # 5-minute timeframe (Pandas Resampling Rule)
      label: "left"                    # Label (timestamp) assigned to each resampled interval comes from the left (start) edge of the window
      closed: "left"                   # Window is left-inclusive, right-exclusive
      source: "1m"                     # Uses 1m timeframe as input (defines the cascading order)
    15m:
      rule: "15T"                      # 15-minute timeframe
      label: "left"
      closed: "left"
      source: "5m"                     # Uses 5m timeframe as input
    30m:
      rule: "30T"                      # And so on....
      label: "left"
      closed: "left"
      source: "15m"
    1h:
      rule: "1H"
      label: "left"
      closed: "left"
      source: "30m"
    4h:
      rule: "4H"
      label: "left"
      closed: "left"
      source: "1h"
    8h:
      rule: "8H"
      label: "left"
      closed: "left"
      source: "4h"
    1d:
      rule: "1D"
      label: "left"
      closed: "left"
      source: "8h"
    1W:
      rule: "W-MON"                    # Weekly, aligning candle close to Monday
      label: "left"
      closed: "left"
      source: "1d"
    1M:
      rule: "MS"                       # Monthly, beginning of the month
      label: "left"
      closed: "left"
      source: "1d"
    1Y:
      rule: "AS"                       # Annual, beginning of the year
      label: "left"
      closed: "left"
      source: "1M"

  # Support per symbol overrides
  symbols:
    includes:
    - path/file/to/include/*.yaml     # You can include files in any key using this pattern
    BTC-USDXX:
      # Override number of decimal places to round to
      round_decimals: 12
      # Override batch size
      batch_size: 500000
      # Skip timeframes entirely for this symbol
      skip_timeframes: ["1W", "1M", "1Y"]
      # Support for custom timeframes or overrides
      timeframes:
        5h:
          rule: "5H"             # 5-hourly timeframe
          label: "left"
          closed: "left"
          source: "1h"
        1d:
          rule: "1D"
          label: "right"         # Different labeling for this specific symbol/timeframe
          closed: "left"
          source: "8h"
```