MT4 is decoded. 

**Notice:** The main branch is now locked. No further modifications will be made to the core codebase unless a critical bug is discovered, a significant feature is released, or an essential security announcement is required. New features are coming.

## Notice: Performance

Performance update was applied. Eliminating IO.tell() and switching the input stream to binary mode, bypasssing the Python "Text-IO" translation layer. Quite a nice improvement.

**Note:** Another major performance update is coming—this one’s a big deal.

Previously, we determined a session’s origin by passing a datetime into a tracker object line by line, returning an adjusted origin for each entry. This approach is extremely CPU-intensive and slow. I’m now working to convert this logic to a vectorized approach, where the line-by-line path is only used for crash safety (specifically, byte-offset tracking). Gain: 23 seconds to 8.5 seconds.

```s
Old:
   Ordered by: cumulative time
   List reduced from 1364 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.010    0.010   23.317   23.317 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:697(run)
        9    0.018    0.002   23.302    2.589 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:741(_execute_engine)
       16    3.592    0.224   17.207    1.075 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:410(prepare_batch)
  2513044    4.618    0.000   11.667    0.000 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/helper.py:68(get_active_session) <!-- bottleneck
       16    0.003    0.000    4.199    0.262 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:528(process_resample)
       16    0.000    0.000    2.762    0.173 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/readers.py:814(read_csv)
       16    0.046    0.003    2.761    0.173 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/readers.py:540(_read)
       16    0.000    0.000    2.147    0.134 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/readers.py:1688(read)
       16    0.000    0.000    2.103    0.131 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/c_parser_wrapper.py:222(read)
...

New:
   Ordered by: cumulative time
   List reduced from 1364 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.008    0.008    8.696    8.696 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:697(run)
        9    0.011    0.001    8.683    0.965 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:741(_execute_engine)
       16    0.002    0.000    3.733    0.233 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:528(process_resample) <!-- already optimized
       16    1.901    0.119    3.025    0.189 /home/jpueberb/repos2/bp.markets.ingest/dukascopy/etl/resample.py:410(prepare_batch) <!-- already optimized
       16    0.001    0.000    2.754    0.172 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/readers.py:814(read_csv)
       16    0.048    0.003    2.752    0.172 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/readers.py:540(_read)
       16    0.000    0.000    2.170    0.136 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/readers.py:1688(read)
       16    0.000    0.000    2.129    0.133 /home/jpueberb/.local/lib/python3.8/site-packages/pandas/io/parsers/c_parser_wrapper.py:222(read)
```

I’m optimizing the resampler so the Panama-adjusted view renders much faster. It used to take 30–40 seconds; now it’s down to about 12.

There is not much more to gain -for the python version that is. So wrapping up.

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

I have some things to do today. Will be finalized tomorrow. Late noon.

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

