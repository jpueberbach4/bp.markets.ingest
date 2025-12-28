MT4 is decoded. 

**Notice:** The main branch is now locked. No further modifications will be made to the core codebase unless a critical bug is discovered, a significant feature is released, or an essential security announcement is required. New features are coming.

**Note:** Another great example on "candle policies"

The policy AUS.IDX, before 2024-06-17 is to have, on monday, 00:00, 04:00 and 08:00 candles in MT4. 

**Example*:*

```sh
MT4 has:

2024.06.14,18:10,7677.627,7696.347,7674.167,7695.473,2097
2024.06.14,22:10,7695.909,7708.981,7694.047,7706.637,513
2024.06.17,00:00,7708.595,7730.457,7697.605,7728.755,1161 <<
2024.06.17,04:00,7728.159,7728.159,7704.657,7713.469,2418 <<
2024.06.17,08:00,7713.491,7717.197,7675.119,7691.221,3073 <<
2024.06.17,14:10,7691.263,7699.703,7674.603,7698.713,1772

We have:

2024-06-14 18:10:00,7677.627,7696.347,7674.167,7695.473,0.2718
2024-06-14 22:10:00,7695.909,7708.981,7694.047,7706.637,0.06638 
2024-06-17 02:50:00,7708.595,7730.457,7697.605,7719.657,0.875705 <<
2024-06-17 06:50:00,7718.657,7723.999,7696.599,7705.657,0.5765 <<
2024-06-17 10:10:00,7709.815,7717.197,7675.119,7691.221,0.203699 <<
2024-06-17 14:10:00,7691.263,7699.703,7674.603,7698.713,0.15754

Incoming 1m feed has:

2024-06-14 23:55:00,7705.031,7705.031,7705.031,7705.031,0.00013
2024-06-14 23:56:00,7705.499,7705.999,7705.499,7705.999,0.00026
2024-06-14 23:57:00,7706.531,7706.531,7706.531,7706.531,4e-05
2024-06-14 23:58:00,7707.031,7707.031,7706.073,7706.073,0.00012
2024-06-14 23:59:00,7706.509,7706.947,7704.541,7706.637,0.00062
2024-06-17 02:50:00,7708.595,7708.999,7698.947,7699.605,0.006925  <<
2024-06-17 02:51:00,7698.541,7700.625,7697.605,7700.625,0.00524
2024-06-17 02:52:00,7699.625,7702.593,7699.625,7702.593,0.00288
2024-06-17 02:53:00,7703.689,7704.999,7702.561,7703.999,0.00336
```

Rest of the week is normal.

I’m wondering how far I should go in replicating MT4 behavior. Our data represents the “ground truth” because it aligns with the exchange, whereas MT4 does not. From 2024-06-17 onward, MT4 does correctly align Monday candles. I could introduce a “valid-on-days-of-the-week” option in the session configuration, but that risks overengineering.

That said, forcing a 00:00 alignment when there is no actual market volume effectively creates “phantom” candles or signals, which I strongly dislike. However, as with most things, this should be configurable rather than impossible to support.

**Decision:** screw it—let’s add the valid-on-weekdays configuration.'

**Update:** This is a hard change. Post-processing steps need to become "session"-aware. The problem here is that MT4 makes the H4 08:00 candle 6 hours and 9 minutes long. There is another gap from 12:00 to 14:09, with data, that creates a "ghost candle". Merging this ghost-candle into the 08:00 solves it, but I cannot do this globally, like with the SGD, because it only should happen on weekday Monday. I need to lay an egg on this one first. Or two.

If you want to see this for yourself, openup the H4 AUS.IDX index, scroll to 2024-06-17 0800. Next H4 candle you see is 14:10. Now go to H1 chart. See candle at 12:10 and 13:10. See close of 13:10 hourly candle, its also close of that H4 08:00 candle. 7691.221. 

I mean, imagine, what these kind of things mean for your backtests in MT4. Its completely fragile.

## Notice: Performance

Two performance improvements have been implemented:

- Streamlined I/O – Replaced IO.tell() in text mode by switching the input stream to binary mode, bypassing Python’s text-IO translation layer.
- Vectorized session handling – Origins are now assigned using vectorized operations instead of line-by-line computation.

At this stage, further performance gains in Python are minimal. Any additional optimization would require switching from CSV to a custom binary format. However, this would sacrifice the transparency and human-readability of CSVs, so it will not be pursued in the Python version. Such optimizations are reserved for the high-performance, tick-ready, C++ variant.

For reference, resampling 42 symbols takes about 1 minute and 30 seconds in Python. A C++ implementation with binary format will reduce this to seconds.

Before:

![Image before update](../images/performanceon41symbols.png)

After: 

![Image after update](../images/performanceon42symbols-after-perf-update.png)

This optimization shaved a little over a minute off the resampling step, yielding roughly a 40% performance improvement.

## Notice: Rollover

Rollover support is being implemented. Programmatic detection was too inaccurate. Different approach was needed.

I have a first version of back-adjustment (Panama) up and running. Severely checking this and parameterizing this before i release it. Initial results look (pretty) good:

```sh
RAW DATA:

December
2025-12-23 20:10:00,62.27,62.27,62.27,62.27,0.000202
2025-12-24 03:00:00,61.922,61.96,61.875,61.88,0.00374
GAP = -0.348

November
2025-11-25 23:39:00,62.552,62.552,62.547,62.547,0.000144
2025-11-26 03:00:00,61.907,61.93,61.83,61.88,0.003438
GAP = -0.64

BACKADJUSTED DATA:

December:
2025-12-23 20:10:00,61.83,61.83,61.83,61.83,0.000202
2025-12-24 03:00:00,61.922,61.96,61.875,61.88,0.00374
GAP = +0.092

November
2025-11-25 23:39:00,61.502,61.502,61.497,61.497,0.000144
2025-11-26 03:00:00,61.467,61.49,61.39,61.44,0.003438
GAP = -0.03
```

By specifying ```SYMBOL:adjusted/TF``` you can optionally decide if you want the Panama-version or the "regular" (default) "broker-reality"-version. It will only support instruments for which a rollover calendar could be found. If it cannot find the calendar, it will stop the builder with a message. 

**Why?**

Raw futures data contains artificial price "gaps" that occur whenever an old contract expires and a new one begins. Panama Adjustment removes these gaps by shifting historical prices to align with the current contract, creating a seamless, continuous price string. Without this adjustment, trading indicators like Moving Averages would be mathematically distorted by "phantom" price jumps that never actually happened in live trading.

Once the 1-minute data is adjusted, all higher timeframes (5m, 1h, Daily) must be resampled from this version to maintain consistency. If you resample from raw data, your hourly or daily candles will contain "dirty" data points from both contracts, resulting in fake candle ranges and incorrect OHLC values. Using the Panama-adjusted 1m source ensures that your multi-timeframe analysis is accurate and that a signal on the 5m chart matches the price action on the 1h chart. Essentially, this process preserves the true "geometric shape" of the market across all intervals. This allows for reliable backtesting and strategy development over long periods.

Ofcourse everything is fully automated. Just a flag is needed to trigger it. The system will be working about 30-40 seconds on 6 panama-adjusted symbols (this unoptimized. optimization steps still need to get performed).

Examples:

Before Panama

![25 november BRENT before backadjust](../images/backadjust/20251125-brent-before-backadjust.png)

After Panama

![25 november BRENT after backadjust](../images/backadjust/20251125-brent-after-backadjust.png)

Completely different perspective. As you can see.

~~I have some things to do today. Will be finalized tomorrow. Late noon.~~ Tomorrow.

**Note:** This only applies to futures traders. Commodities, Bonds, Indices. For Forex and Crypto it will just skip the logic if you specify it. The ```adjusted``` modifier will then only just print a warning - that you are trying to apply it for an instrument where its not necessary.  

## Notice: Backfilling

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

