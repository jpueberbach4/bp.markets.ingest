## Status per 19 December 2025

**Note:** The data part is not finished yet. Still bugs/features to resolve:

- Soybean 1Y timeframe throws out_of_market error 1Y timeframe disabled on that asset Happens because of timezone America/Chicago and start of month being on a Sunday. \
  Who trades it anyways, but will get fixed.
- ~~Compatibility for "alignment policy changes" in MT4 eg for AUS.IDX-AUD \
  Adding valid_from, valid_to attributes on sessions to allow for different session allocation for specific dateranges.~~
- Strange quirk with the SGD.IDX. H4 \
  1m data is present, outside of 4H timeframes, creating a candle we dont see in MT4. What to do with it? (research)
- Sessions are currently mapped, fixed, to America/New_York. \
  Make it based on the symbol's timezone setting in transform.timezones.
- Perhaps other things.... 

It's a limited list. Looks actually pretty good.

This is "reverse engineering" of the MT4 platform.

**Note:** The ETL part of this project has been converted to OOP. Making it slightly less readable but better maintainable and testable.

**Note:** This system is more and more getting tailored to Dukascopy. I dont have time to test this with other brokers like FXCM or IGMarkets. Chances are, that these brokers have different rules regarding to the assets they "broker for". Different alignment policies, etc. The system can be used with other brokers since the 1m base data should be near equal at any broker. Prices are factual, market-wide. If differences: you will have to tailor it to these brokers yourself. It's a tedious job but the reward is there if you succeed.

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
