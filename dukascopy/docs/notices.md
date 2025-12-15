## Notice

**Dukascopy has reviewed this and cleared it. However, we ask you to behave as a good citizin. Thank you**

>Rate limits have been added, see [here](#downloads-appear-slower-after-updating-to-the-latest-version)

⚡ Branch guide:

- main and other branches: bleeding-edge, early access
- releases: stable, less functionality

❗ WARNING: Are you on MT4? CHANGE ```time_shift_ms```. When changing ```time_shift_ms``` while already having a dataset, execute ```./rebuild-full.sh```

Time shifts cannot be applied incrementally because timestamps affect all aggregation boundaries.

>I’m building a **Dukascopy** MT4–tailored configuration file, ```config.dukascopy-mt4.yaml```. You can review it to get a sense of how this configuration file is structured and how it can be extended. If you are using an other broker, you can use the file for reference.

>When you apply ```config.dukascopy-mt4.yaml```. Perform a rebuild from scratch ```./rebuild-full.sh```.

## Notice

**Dukascopy Time Zone Drift (DST Issue)**

The Dukascopy MT server switches between GMT+2 (standard time) and GMT+3 (daylight saving time based on America/New_York timezone), which caused historical OHLC candles to be misaligned and incorrectly binned. A fix has been implemented in the transform layer to correctly handle this behavior.

If you are working with Dukascopy MT4, copy the timezones block from ```config.dukascopy-mt4.yaml``` into your ```config.user.yaml```, then run ```./rebuild-full.sh```.

Note that the configuration is not yet complete and may change again in the future as support for additional symbols is added.

The solution has been tested on BRENT, and weekly candles are now correctly aligned. Performance impact of fix is limited, so no additional performance tuning regarding the new logic will be done.

```sh
transform:
  time_shift_ms: 7200000              # How many milliseconds should we shift (0=UTC, 7200000=GMT+2 (eg MT4 Dukascopy))
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
      symbols:                --!>    # Basically you add any symbol you are using here. <!--
      - SYMBOL1               --!>    # Investigation about Crypto is ongoing.           <!--
      - SYMBOL2
```

To me, it's not exactly clear how Crypto is handled. I have sent an e-mail.


## Notice

Backfilling is not currently supported, as our pipeline processes data strictly forward. Because of this, historical data—particularly for illiquid pairs and at the highest granularity—may be skewed. Backfilling has been identified as a must-have feature.

We'll provide a script that should be executed once every seven days (run on saturdays). It will re-download the past week of data for all configured symbols and perform a full rebuild. This captures any backfills within that window, effectively addressing ~99.94-99.97% of all backfill issues.

For reference, running this on 26 symbols takes about five minutes (or around 2 minutes 30 seconds if you’re up to date and use the rebuild script)—a small price to pay for accuracy.

```python
Major FX         █░░░░░░░░░ 0.01%  (1 in 7,000-12,500 symbol-days)
Major Crosses    ███░░░░░░░ 0.05%
Illiquid FX      ██████████ 1.1%
Indices          ██░░░░░░░░ 0.09%
Major Crypto     ██████████ 1.3%
Altcoins         ████████████████ 3.5%
```

```sh
crontab -e
```
Add the following line, adjust path accordingly:

```sh
0 1 * * 6 cd /home/repos/bp.markets.ingest/dukascopy && ./rebuild-weekly.sh
```

This configuration triggers the rebuild script at 01:00 each Saturday. It will not conflict with the per-minute ./run.sh cron entry (due to locking). For additional assurance, you may choose to run it daily. Overall, the setup is now far more robust in terms of integrity.

>This is a universal challenge in market-data engineering. Even when working with top-tier, premium data vendors, the moment you download or extract data and begin using it, some portion of it may already be stale due to backfills. It’s an inherent property of financial datasets, not a limitation of this tool. There is no central log or official feed that reliably exposes all historical corrections, making automated detection non-trivial. As a result, every data pipeline—paid or free—must contend with this reality.

The quality of this dataset is on par with what you would receive from commercial providers. The difference is simply that this one is free.
