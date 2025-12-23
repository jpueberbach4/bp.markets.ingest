MT4 is decoded

## Status per 23 December 2025

I’m currently finishing up the ETL/data work, which will be completed before Christmas. Once that’s done, the main branch will become stable, and new features will be developed through regular feature branches. The code is now used by many people, so stability is crucial. That said, daily repository statistics are still being merged into main, and there’s a specific reason for this approach.

also...

I am strengthening the setup and this also includes an OHLCV validation check. You can enable this check using the ```transform.validate``` flag in config.user.yaml. Currently it only prints if it finds anything "out of the ordinary". During testing, i ran the validation step, here is what i found:

**Data Validation Error Count**

Total Errors: 94

Breakdown by Symbol:

- AUD-USD: 57 errors \
  Time period: 2008-09-18 to 2024-10-10 \
  Primarily clustered in 2008-2009 (financial crisis period)
  
- LIGHT.CMD-USD: 32 errors \
  Time period: 2013-10-03 to 2014-06-06 \
  Heaviest concentration in Q1-Q2 2014

- VOL.IDX-USD: 19 errors \
  Time period: 2022-10-06 to 2025-12-22 \
  Recent data (2022-2025)

- SOA.IDX-ZAR: 8 errors \
  Time period: 2022-10-06 to 2022-10-25 \
  October 2022 specifically

- COPPER.CMD-USD: 6 errors \
  Time period: 2014-10-13 to 2014-11-27 \
  Q4 2014

- BRENT.CMD-USD: 1 error \
  2014-08-01

- BTC-USD: 1 error \
  2017-09-04

- COTTON.CMD-USX: 1 error \
  2017-10-20

- Other FX pairs on 2024-10-10: 6 errors \
  EUR-USD: 1 \
  USD-JPY: 1 \
  GBP-USD: 1 \
  USD-CHF: 1 \
  NZD-USD: 1 \
  EUR-NZD: 1

Time Distribution:

- 2008-2009: 57 errors (AUD-USD during financial crisis)
- 2013-2014: 39 errors (commodities data issues)
- 2017: 2 errors (crypto & cotton)
- 2022-2023: 27 errors (indices)
- 2024-2025: 7 errors (recent FX & indices)

Error Type Analysis:

All errors are "OHLC Integrity Failure" with variations:

- High price below Low price (most common)
- High price below Open or Close
- Low price above Open or Close

Context:

- Total files processed: 321,804
- Error rate: 94/321,804 = **0.029% (extremely low)**
- Processing speed: ~940 files/second (validation slows a lot)

Time to process: 5 minutes 42 seconds

>Currently it only logs if the flag is set to true. In a later version skip, log (true fallback), break and correct (or combinations) will be supported.

Additionally, custom exceptions and fsync flag are introduced. Fsync increases data durability at the expense of performance. Use wisely. I don't use it, since a full rebuild just takes little time, on my setup. But if you are running many symbols, after initial run, you might want to set fsync to true on all stages.

## Status per 22 December 2025

Volumes will be left as how they are. It's very meaningful data as how it is.

There is multiplication support built but don't use it. I will leave the software in place for later, eg. optional, pre- and post-processing steps.

Still open: Sessions are currently mapped, fixed, to America/New_York. Make it based on the symbol's timezone setting in transform.timezone. This is a cosmetic issue since the '*' select is present on the timezone America/New_York in ```config/dukascopy/timezones/america-new_york.yaml```. The fix is needed to support users who wish to use advanced session settings on eg ```Etc/UTC```.

New item: more granular exception handling using custom exceptions

## Status per 21 December 2025

Starting to get very pleased with the results of this effort. I have now seen about everything what MT4 does and doesnt. Quite a learning experience with some interesting conclusions derived from it. Especially the SGD index has opened my eyes. As far as i can see, we are nearing 100 percent correctness (we are very close). If anything, i may have missed, or overlooked, or anything else,.. dump a message in the discussions.

I don't think there is anything that can't be solved regarding to alignment. This project was able to solve it in little more than 800 lines where a large part of it, is preparing the configuration structure (the overrides, the defaulting etc).

If you want to see how many clones this project has. See the workflow directory. This project is really a problem solver for a lot of people.

Fixing the volume (what factor, is it per symbol, or "system-wide"?) is now the only high priority item left and that will be done tomorrow.

!!! BUG !!!

**There was/is a bug in the get_active_session. The bug was not visible because exceptions got swallowed silently because of the large OOP refactor. Now that i made them visible, this became clear. A quickfix is in. You will need to copy-over the configs using ```./setup-dukascopy.sh```. This also fixes the SOYBEAN 1Y issue.**

Various bug-fixes and updates:

>**To update: ```git checkout main && git pull origin main```**

After update: ```./rebuild-resample.sh``` (only if you have SGD.IDX/AUS.IDX/HKG.IDX)

**Note:** SGD issue has been fixed - [SGD-indices.yaml](../config/dukascopy/timeframes/indices/SGD-indices.yaml).

Still open: Sessions are currently mapped, fixed, to America/New_York. Make it based on the symbol's timezone setting in transform.timezone. This is a cosmetic issue since the '*' select is present on the timezone America/New_York in ```config/dukascopy/timezones/america-new_york.yaml```. The fix is needed to support users who wish to use advanced session settings on eg ```Etc/UTC```.


## Notice

**Dukascopy has reviewed this and cleared it. However, we ask you to behave as a good citizin. Thank you**

>Rate limits have been added, see [here](#downloads-appear-slower-after-updating-to-the-latest-version)

⚡ Branch guide:

- main and other branches: bleeding-edge, early access
- releases: stable, less functionality

>I’m building a **Dukascopy** MT4–tailored configuration file, ```config.dukascopy-mt4.yaml```. You can review it to get a sense of how this configuration file is structured and how it can be extended. If you are using an other broker, you can use the file for reference.

>When you apply ```config.dukascopy-mt4.yaml```. Perform a rebuild from scratch ```./rebuild-full.sh```.

**Update (19 december)**: When you use the above configuration you get nearly EXACT simulation of the candles in Dukascopy MT4. 

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
