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

Labelling:
```sh
                        open     high      low    close  volume origin   offset
time
2025-12-19 08:30:00  436.599  436.756  436.241  436.550  0.1284  02:30  2510929
2025-12-19 09:30:00  436.447  436.859  436.241  436.644  0.1344  02:30  2510987
2025-12-19 10:30:00  436.556  436.999  436.253  436.750  0.3180  02:30  2511046
2025-12-19 11:51:00  436.444  436.999  436.444  436.847  0.1692  >>15:51<<  2511103
2025-12-19 12:51:00  436.959  436.959  436.299  436.756  0.1284  >>15:51<<  2511162
2025-12-19 13:51:00  436.850  436.899  436.341  436.556  0.1752  >>15:51<<  2511221
2025-12-19 14:51:00  436.453  437.299  436.353  437.156  0.2592  >>15:51<<  2511279
2025-12-19 15:51:00  437.299  438.799  437.141  438.359  0.5280  15:51  2511338
```

That's interesting. Tricky issue. Merging seems a better option. Merging is in fact THE ONLY option, for this current design (without bloating the code). Even if we could fix the labelling to 02:30 for the 11:51:00, 12:51:00, 13:51:00,... we would still be stuck with that 2025-12-19 14:51:00 which falls outside of the range 10:30:00-14:30:00 (The H4 candle at 10:30) and before the 2025-12-19 15:51:00 (The H4 candle at 15:51).
It would fall into a GAP, which then would still create a ghost-candle, only with different values. 

**Decision:** small postprocesssing step when merge is defined. Merging the 2025-12-19 11:51:00 ghost candle into the 2025-12-19 10:30:00 candle.

Have a working fixed-code fix:

```python
# testing
if self.ident == "4h":
    ghost_positions = np.where(full_resampled.index.str.endswith("11:51:00"))[0]

    print(ghost_positions)
    for pos in ghost_positions:
        # Ensure there is a row before the ghost to merge into
        if pos > 0:
            ghost_idx = full_resampled.index[pos]
            anchor_idx = full_resampled.index[pos - 1]
            full_resampled.at[anchor_idx, 'high'] = max(full_resampled.at[anchor_idx, 'high'], full_resampled.at[ghost_idx, 'high'])
            full_resampled.at[anchor_idx, 'low'] = min(full_resampled.at[anchor_idx, 'low'], full_resampled.at[ghost_idx, 'low'])
            full_resampled.at[anchor_idx, 'close'] = full_resampled.at[ghost_idx, 'close']
            full_resampled.at[anchor_idx, 'volume'] += full_resampled.at[ghost_idx, 'volume']
            # We remember the offset of the 10:30 candle. Will be interesting to see how MT4 handles this during that candle
            # formation. We will see next week.

    # drop all ghosts
    full_resampled = full_resampled[~full_resampled.index.str.endswith("11:51:00")]
```

This works. The pointer logic is actually beautiful. Now make this timezone-aware, map this to a configuration structure and it's done.

```sh
2025-12-17 02:30:00,439.759,439.899,435.447,437.044,1.446
2025-12-17 06:30:00,436.947,439.299,436.541,439.159,0.5724
2025-12-17 10:30:00,439.25,440.056,438.944,439.744,0.6696
2025-12-17 15:51:00,439.659,440.299,435.841,436.344,3.7788
2025-12-17 19:51:00,436.453,436.856,434.656,434.753,1.4592
2025-12-18 02:30:00,435.747,437.044,433.953,434.447,1.4484
2025-12-18 06:30:00,434.547,435.444,434.341,434.959,0.5136
2025-12-18 10:30:00,434.85,437.199,434.35,436.753,0.8616
2025-12-18 15:51:00,436.699,438.247,435.847,436.699,2.3928
2025-12-18 19:51:00,436.55,437.499,435.741,436.25,1.7076
2025-12-19 02:30:00,436.247,437.956,435.644,436.347,1.1424
2025-12-19 06:30:00,436.45,436.859,436.041,436.644,0.4968
2025-12-19 10:30:00,436.556,437.299,436.253,**437.156**,1.05
2025-12-19 15:51:00,437.299,439.199,437.141,438.953,1.7184
2025-12-19 19:51:00,439.053,439.259,437.747,438.05,0.414
```

```yaml
SGD.IDX-SGD:
  timezone: Asia/Singapore
  sessions:
    morning:
      ranges:
      ...
      timeframes:
	    ...
        4h:
          bugs-bunnies:
            ghosts:
               include:
               - 11:51:00       # Needs to be Asia/Singapore local time
          rule: "4H"
          label: "left"
          closed: "left"
          source: "1h"
          origin: "02:30"
```

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