## Status per 22 December 2025

Basic volume modification support through a multiple factor is in. For indices this is very accurate. For others, you will need to determine a median value. Use AI for that. 

Approach:

- Export some 4H bars from history center in MT4 for your asset
- Export some 4H bars using build-csv.sh (see tools section) for your asset
- Take 20 rows from each file (do not use any open candle)
- Make sure timestamps match between files
- Paste both snippers with a header (MT4:file, Tool: file) in a single message 
  to AI and say: "calculate mean and median deviation". It will give you the median,
  apply that in ```processing.yaml``` for the asset. Examples are there.

PS: deepseek is best for this kind of work. You will need to do a ```full-rebuild.sh``` if you change the transform step since it touches the base 1m data. 

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
