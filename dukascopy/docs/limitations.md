## Limitations

While the tool is becoming pretty excellent, it is worth noting that there are (still) some limitations. Not many AFAICS.

### Volumes - **Partly resolved (for (a very few) indices it (seems to) works)**

**Dukascopy is providing the raw contract value, whereas MT4 is providing a count of price updates.**

Conclusion: **cannot fix**

However, i am testing with a fixed multiply factor for indices though. Here the factor seems to be constant.

Oke. For A50 (CHI.IDX) - the multiplier support seems/is good enough.

```yaml
# config/dukascopy/processing.yaml
CHI.IDX-USD:
  post:
    volume-adjust:
      action: multiply
      column: volume
      value: 34484
```

| Time   | Tool Volume      | MT4 Volume | Difference | Ratio (Tool/MT4) |
|--------|------------------|------------|------------|------------------|
| 11:00  | 1,644.059184     | 1,642      | +2.059     | 1.001254         |
| 15:00  | 8,780.316080     | 8,780      | +0.316     | 1.000036         |
| 19:00  | 3,551.127836     | 3,551      | +0.128     | 1.000036         |
| 03:00  | 20,412.734832    | 20,411     | +1.735     | 1.000085         |
| 07:00  | 16,747.602892    | 16,746     | +1.603     | 1.000096         |
| 11:00  | 1,185.042660     | 1,185      | +0.043     | 1.000036         |
| 15:00  | 5,842.210312     | 5,841      | +1.210     | 1.000207         |
| 19:00  | 3,805.136980     | 3,805      | +0.137     | 1.000036         |
| 03:00  | 23,158.833688    | 23,155     | +3.834     | 1.000166         |
| 07:00  | 13,756.495216    | 13,755     | +1.495     | 1.000109         |
| 11:00  | 1,755.063180     | 1,755      | +0.063     | 1.000036         |
| 15:00  | 4,377.157572     | 4,377      | +0.158     | 1.000036         |
| 19:00  | 1,286.046296     | 1,290      | -3.954     | 0.996935         |
| 03:00  | 19,102.687672    | 19,106     | -3.312     | 0.999827         |
| 07:00  | 12,377.445572    | 12,372     | +5.446     | 1.000440         |

- **Average Ratio**: 1.000146 (tool is 0.0146% higher on average)
- **Median Ratio**: 1.000096
- **Range**: 0.996935 to 1.000440
- **Standard Deviation**: 0.000860
- **Mean Absolute Difference**: 1.744 units

This is merged to main. See ```config/dukascopy/processing.yam``` and ```config.dukascopy-mt4.yaml```. If you are still using the default config:  after update, ```./setup-dukascopy.sh```. You see if you apply it also for other instruments. For (only a few) indices this is helpful.

**General advice:** leave the volume column untouched (me? i wont use it).

### Session from-to support - **Solved, merge support is in for SGD, available in main** 

We have implemented the from_date, to_date for sessions. Using these date-times you can determine between
what timestamps a session is valid/active. 

**Fix details:** Small postprocesssing step when ```timeframe.post``` is defined. See SGD config file for the "bugs-bunny" example.

There are still small candles issues on "candle policy change rollover". Very minor. Moved to longer term todo list.

### Session windows - indices, forex with breaks - **solved, implemented, available in main**

Example: AUS.IDX-AUD (index). The Aussie index has 2 trading sessions (for futures and derivatives). 

- Day Session: 9:50 AM - 4:30 PM (AEST) **
- Overnight (After-Hours) Session: 5:10 PM - 7:00 AM the next morning (AEST) **
- There is a short break between sessions (4:30 PM - 5:10 PM).

In MT4 we will see the candles aligning to HH:50 for the first (day) session and to HH:10 for the after-hours (overnight) session.

We have now support for these kind of "custom" trading windows. 

### YAML configuration is becoming huge - **solved, implemented, available in main**

Given the number of “abnormalities” we need to support, the YAML file is at risk of becoming very large. I plan to add support for an include pattern so the configuration can be split into separate files by section, override, and similar concerns.

We have now support for an  ```includes``` subkey. Any glob file-patterns listed within this key are now included.   

This will help organize the configuration a lot better.