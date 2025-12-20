## Limitations

While the tool is becoming pretty excellent, it is worth noting that there are (still) some important limitations which makes 100% support for all sources, currently, not possible.

### Session from-to support - Nitpicking BUT "drop/merge support" can also be useful

We have implemented the from_date, to_date for sessions. Using these date-times you can determine between
what timestamps a session is valid/active. Works like a charm. BUT. Ofcourse something happens when the 
switches happen. Let's take (again) AUD.IDX-AUD as an example. See configuration for this asset in ```config/dukascopy/timeframes/indices/AUD-indices.yaml```. This is what happens when the day-session and after-hours actually becomes active:

```sh
2020-02-06 00:00:00,7036.09,7042.08,7011.16,7018.79,1.218572
2020-02-06 04:00:00,7018.79,7051.07,7018.77,7044.08,2.033202
2020-02-06 08:00:00,7046.27,7054.63,7031.2,7040.72,0.466506       << CANDLE correct OHLC values with MT4
2020-02-06 12:00:00,7040.65,7056.41,7031.21,7053.07,0.260305      << CANDLE correct OHLC values with MT4
                                                                     EXCEPT close. In MT4 close is 7049.02.
2020-02-06 12:10:00,7052.95,7053.41,7039.0,7049.02,0.313945       << WHOOPS. EXTRA CANDLE. DOESNT EXIST IN Mt4
                                                                     CLOSE of this candle is merged with previous candle.
2020-02-06 16:10:00,7049.58,7060.14,7032.04,7051.57,0.96395       << CANDLE correct OHLC values with MT4
2020-02-06 20:10:00,7051.51,7057.51,7045.13,7051.1,0.13875
```

Now, conclusion of this is, that during the switch MT4 has filtered out 1m data between 16:00 and 16:10 and merged it in the previous candle. Because we don't merge atm, it creates a "ghost candle" since the data between 16:00 and 16:10 falls within the 12:10 candle (which becomes active during the switch). 

Now. This is the only candle mismatch in say 10 years,.. so it's nitpicking. BUT. I think it can be useful if we also build "DROP/MERGE/SHIFT-1m candle between from and to datetime/time" support. This will also solve the SGD issues. Yes. MT4 likely just shifts the 1m candles there too (preliminary conclusion though).

I said i want 100 percent correctness, so, yeah... let's just do it. Timezone stuff is very tricky to implement but the basis seems solid now so this feature shouldnt be too hard.

If you want the config change for AUS.IDX-AUD.. copy over the AUD-indices.yaml to your config.user directory. If you choose to do so, you will need to ```./rebuild-resample.sh```. Takes about 3 minutes on 40 symbols (Ryzen 7, NVMe 3).

**Note:** This is a matter of "taste" as well. Some would like to prefer to keep the real day-session and after-hours sessions active, also before FEB 2020, because it's a better "truth". You decide yourself. I am here to align everything 100 pct to MT4.

### Session windows - indices, forex with breaks - **solved, implemented, available in main**

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

### YAML configuration is becoming huge - **solved, implemented, available in main**

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