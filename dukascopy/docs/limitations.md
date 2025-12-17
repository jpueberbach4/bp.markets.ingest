## Limitations

While the tool is becoming pretty excellent, it is worth noting that there are (still) some important limitations which makes 100% support for all sources, currently, not possible.

### Session windows - indices, forex with breaks - **implemented, available in main**

Example: AUS.IDX-AUD (index). The Aussie index has 2 trading sessions (for futures and derivatives). 

- Day Session: 9:50 AM - 4:30 PM (AEST) **
- Overnight (After-Hours) Session: 5:10 PM - 7:00 AM the next morning (AEST) **
- There is a short break between sessions (4:30 PM - 5:10 PM).

In MT4 we will see the candles aligning to HH:50 for the first (day) session and to HH:10 for the after-hours (overnight) session.

We will need (and are going to) support these kind of "custom" trading windows. 

Implementation will happen in resample.py, configurable via YAML.

**Implementation details:** 

In resample.resample_batch(sio): 

- read custom origin conditional rules with time-boundaries
- if defined, prefilter for each rule based on time-boundary of rule, determine origin, filter data
- push filtered data + data-specific origin to df.resample
- any remaining data left? prefilter again with alternative rules, repeat
- any remaining data but filters comeup empty? fallback to default

(ofcourse, this needs to be timezone-aware)

Until this fix has been implemented, the AUS.IDX-AUD is not really usable.

**Note:** There is still a fix needed for candle alignment policy changes. This will be ready soon too.

**Update:** Found the right approach: insert the (calculated) origin directly into the DataFrame. The origin is computed per row in resample_batch_read. I’ll need another day to handle the remaining edge cases—for example, before ~6 February 2020 a completely different alignment (“era”) was in effect. It’s starting to look promising. The current approach can also be flattened so it works for non-exotic sessions as well. Overall it’s roughly one extra vectorized operation in exchange for much cleaner and more unified code. For 2025 i have perfect alignment for AUS.IDX-AUD (1h, 4h, all of them). 


### YAML configuration is becoming huge - **implemented, available in main**

Given the number of “abnormalities” we need to support, the YAML file is at risk of becoming very large. I plan to add support for an include pattern so the configuration can be split into separate files by section, override, and similar concerns.

Example:

```yaml
transform:
  time_shift_ms: 7200000              # How many milliseconds should we shift (0=UTC, 7200000=GMT+2 (eg MT4 Dukascopy) )
  round_decimals: 8                   # Number of decimals to round OHLCV to
  paths:
    data: data/transform/1m           # Output directory for transform
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
  timezones:
    includes:
    - config/timezones/America-New_York.yaml
...
resample:
  round_decimals: 8                   # Number of decimals to round OHLCV to
  batch_size: 250000                  # Maximum number of lines to read per batch
  paths:
    data: data/resample               # Output directory for resampled timeframes
  timeframes:
    includes:
    - config/resample/default.rules.yaml
  # Support per symbol overrides
  symbols:
    includes:
    - config/resample/symbols/BUND.TR-EUR.yaml
    - config/resample/symbols/BRENT.CMD-USD.yaml
    - config/resample/symbols/*-USD.yaml

```

This will help organize the configuration a lot better.