MT4 is decoded.

## Notice: Data

**Note:** I can only adjust data that is actually “viewable”. For example, for AUS.IDX, I can see H4 candles from 2019-12-01 to the present. What happened before 2019-12-01 is essentially a black box. I simply assume that the first detected candle policy also applies to the data preceding the viewable period. This is logical but nevertheless worth mentioning.

The data portion is now (fairly) complete. Naturally, some QA issues remain, particularly in the builder component, which will be addressed over time. Ensuring optimal QA for the ETL process takes priority over the extraction utility itself.

Of course, testing is an ongoing process. Markets are quiet at the moment, so I’ll continue next year. Happy New Year to everyone! 🎉

## Notice: 2020 MT4-side anomaly ASX

I discovered that some manual patching was applied on the MT4 server side in 2020 for AUS.IDX (see [ASX "forensics"](forensics/ASX.MD)). I built a small test framework to evaluate the performance impact of replicating this “anomaly” via pre-processing during the resampling step.

I introduced a time-shift pre-processing step and was able to align the 1-minute data with the anomaly, but the performance impact was significant. As a result, a pre-process/resample-based solution is not viable.

(The performance impact stems from redefining the 1-minute data as a “raw” timeframe and then rebuilding a custom 1-minute timeframe via a resampling step with preprocessing rules. This effectively creates a shifted copy of the raw data via resampling, which is where the performance degradation occurs.)

If I decide to replicate this behavior, it will get implemented in the transform step, which would require a full rebuild. It is still unclear whether this behavior was server-wide or limited to this asset only. This is something to revisit next year.

## Notice: Panama backadjustment "Public beta" live

I’ve implemented an initial version of the Panama backadjustment logic. It’s now available for you to try, although I’m still rigorously testing it myself. At the moment, rollover adjustments are supported for *-USD commodities. I have tested it with:

- BRENT.CMD-USD
- GAS.CMD-USD
- LIGHT.CMD-USD
- DIESEL.CMD-USD

For these symbols, the adjustment works beautifully. Since Dukascopy applies rollovers at the end of the day, implementing this solution turned out to be much simpler than expected.

I cannot guarantee flawless performance for symbols outside of those tested, which is why the feature is currently in a “public beta” state.

Below is a general explanation of Panama backadjustment and why it is widely used by retail traders, generated with the help of AI:

Panama backadjustment is a method used mainly for futures contracts to create a continuous price series across contract rollovers. When one futures contract expires and trading moves to the next, there is often a price gap caused by differences in contract pricing, not real market movement. Panama backadjustment removes these artificial gaps by calculating the price difference at each rollover and applying cumulative offsets to historical prices.

This is important to traders because it produces clean, continuous charts that preserve true price action, trends, and technical indicator behavior. It is commonly used for technical analysis, backtesting trading strategies, risk modeling, and signal generation, where unadjusted rollover gaps would otherwise distort indicators, trigger false signals, or break historical comparisons.

**Note:** Panama backadjustment modifies the 1-minute base data and resamples all higher timeframes to ensure they align with the adjusted base. The process takes some time, but for most symbols it typically completes in under 30 seconds, depending on your hardware.

Examples:

```sh
./build-csv.sh --select BRENT.CMD-USD:panama/1m --output panama-test.csv
```

Before Panama

![25 november BRENT before backadjust](../images/backadjust/20251125-brent-before-backadjust.png)

After Panama

![25 november BRENT after backadjust](../images/backadjust/20251125-brent-after-backadjust.png)

Completely different perspective. As you can see.

**Note:** This only applies to futures traders. Commodities, Bonds, Indices. For Forex and Crypto it will just skip the logic if you specify it. The ```panama``` modifier will then only just print a warning - that you are trying to apply it for an instrument where its not necessary. 

**Note:** Panama-adjusted data may show negative prices in the distant past. This is normal and expected. Please ensure your backtesting framework can handle such values. If you want to know how to deal with this/when this is a problem, just copy the previous sentence to Gemini and it will guide you.



## Notice: Pre- and Post Processing steps now "session-bound"

You’re now able to configure pre- and post-processing steps within sessions that are constrained by the session’s logical boundaries (weekdays and date ranges). This is a general code improvement that should have been done anyway, regardless of whether the AUS.IDX issue was the original motivation.

Config example:

```yaml
AUS.IDX-AUD:
  timezone: Australia/Sydney
  skip_timeframes: []
  sessions:
    my-very-special-aussie-handler:
      # This is a special candle-alignment handling for the AUS.IDX. 
      weekdays: [0] # 0=monday, 1=tuesday, and so on..
      to_date: "2024-06-22 01:00:00"  # In Australia/Sydney time
      ranges:
        day: 
          from: "09:50"
          to: "17:09"
      timeframes:
        4h:                     
          origin: "epoch"
          post:
            # On Mondays, and up to 2024-06-24, candles must be aligned to 00:00 (epoch).
            # The 08:00 candle on these Mondays spans 6h10m instead of 4h, due to data
            # existing between 12:00 and 14:10. This creates a “ghost” H4 candle at 10:10,
            # which must be merged into the previous candle (the 08:00 H4 candle).
            # MT4 charts are fragile, but this ensures exact alignment for users who
            # choose to enable it. When DST has shifted, also a 09:10:00 candle needs to 
            # get cleaned.
            merge-step:
              action: merge
              ends_with:
              - "09:10:00"
              - "10:10:00"
              offset: -1  
```

The software is become more and more powerful to handle edge-cases and MT4-anomalies. This is a change for the better.

**Note:** I removed a previous notice, which should have been kept in. The above example can easily be verified. I claim that the 2024-06-17 08:00 H4 candle is actually 6h10m long. I want to show this, because it needs to be very clear what this means. You can load the H4 AUS.IDX and browse to that candle by holding down page-up. When you have found it, look at it's closing price. It's 7691.221. Now open-up the H1 chart. Locate the H1 candle 2024-06-17 13:10, which closes at 14:10, It's close price is 7691.221. Conclusion, this "H4" candle is actually 6h10m long and contains liquidity and price action which falls outside of an regular H4 boundary. I consider this stuff "spooky".

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

