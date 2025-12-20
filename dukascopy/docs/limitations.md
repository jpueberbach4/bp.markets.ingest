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

**Note:** I will have to estimate what happens with AUS.IDX-AUD on the lower TF's since i cannot access date 2020-02-06 on the hourly and lower timeframes. I will use the recent behavior of SGD to implement that ghost-candle fix also for AUS.IDX-AUD. SGD's behavior will become the "definition" for this fix.

SGD issue:

H4 candles (10:30 and 11:51 incorrect)
```sh
2025-12-19 06:30:00,436.45,436.859,436.041,436.644,0.4968
2025-12-19 10:30:00,436.556,436.999,436.253,**436.75**,0.318     << IN MT4, the close of this candle is 437.156
2025-12-19 11:51:00,436.444,437.299,436.299,^^437.156^^,0.732    << GHOST CANDLE
2025-12-19 15:51:00,437.299,439.199,437.141,438.953,1.7184
2025-12-19 19:51:00,439.053,439.259,437.747,438.05,0.414
```

Metatrader H4:
```sh
2025.12.19,06:30,436.450,436.859,436.041,436.644,414
2025.12.19,10:30,436.556,437.299,436.253,^^437.156^^,875
2025.12.19,15:51,437.299,439.199,437.141,438.953,1432
2025.12.19,19:51,439.053,439.259,437.747,438.050,345
```

H1 candles (correct):
```sh
2025-12-19 10:30:00,436.556,436.999,436.253,**436.75**,0.318
2025-12-19 11:51:00,436.444,436.999,436.444,436.847,0.1692
2025-12-19 12:51:00,436.959,436.959,436.299,436.756,0.1284
2025-12-19 13:51:00,436.85,436.899,436.341,436.556,0.1752 
2025-12-19 14:51:00,436.453,437.299,436.353,^^437.156^^,0.2592 
2025-12-19 15:51:00,437.299,438.799,437.141,438.359,0.528
```

Metatrader H1:
```sh
2025.12.19,10:30,436.556,436.999,436.253,**436.750**,265
2025.12.19,11:51,436.444,436.999,436.444,436.847,141
2025.12.19,12:51,436.959,436.959,436.299,436.756,107
2025.12.19,13:51,436.850,436.899,436.341,436.556,146
2025.12.19,14:51,436.453,437.299,436.353,^^437.156^^,216
2025.12.19,15:51,437.299,438.799,437.141,438.444,441
```


That's interesting. It's not only shift support but also seems a labelling issue. 

```yaml
SGD.IDX-SGD:
  timezone: Asia/Singapore
  skip_timeframes: []
  sessions:
    day-session:
      ranges:
        open:
          from: "08:30"
          to: "17:20"
      timeframes:
        ...
        4h:
          shifts:
            every-day:
              # The following two parameters are needed to fix the AUS.IDX only at specific date
              from_date: 1970-01-01 00:00:00 (optional)
              to_date: 3000-01-01 00:00:00 (optional)
              # The following three values are only needed for SGD
              # 1H candle falls in between these two times (17:30 Asia/Singapore time)
              from: 17:20           # Time in Asia/Singapore
              to: 17:50             # Time in Asia/Singapore
              value_ms: -1800000    # SHIFT left, 30 minutes
          rule: "4H"
          label: "left"
          closed: "left"
          source: "1h"
          origin: "02:30"
```

This is preliminary. Need to think this over once more.

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