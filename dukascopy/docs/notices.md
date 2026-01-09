<u>MT4 is decoded.</u>


## Notice: Version 0.6.5 may be a breaking change version - 2026-01-09

When you update to this version, it will break the API when its running. You need to `./service.sh stop`, then update, then `./service.sh start`.

What you get from this new version:

- [Binary](binary.md) or text mode
- 11x increased resampling performance in binary mode
- About 10x increase on performance on API calls in binary mode
- Cleaner HTTP service code
- [Abstracted IO](io.md) layer
- I/O bound performance in binary mode
- Configuration validation using schema
- Unchanged behavior on builder utility

When you change to this version, choose either `binary/text` mode. Default is still text-mode to try not to break existing installations but i cannot guarantee that it will not happen. The index files now hold 3 fields instead of two. I did build in backward compatibility. 

If you notice any errors, solution is simple `./rebuild-full.sh`. 

Most users will appreciate the binary version because of its increased performance. If you choose binary, make sure to set all the `fmode` fields to binary-also for transform, aggregate, http and resample. If you are still using the default setup `./setup-dukascopy.sh`, then edit the `config.user.yaml` and CTRL+F fmode and change all `text` values to `binary`. Next, perform a `./rebuild-full.sh`.

| Operation | CSV Mode | Binary Mode | Speedup |
| :--- | :--- | :--- | :--- |
| **Transform** | 6.00s | 1.20s | 5x faster |
| **Aggregate** | 2.76s | 3.05s | (Slightly slower - optimizing) |
| **Resample** | 28.14s | 2.52s | **11x FASTER!** 🎉 |
| --- | --- | --- | --- |
| **TOTAL** | **38.42s** | **6.77s** | **5.0x FASTER OVERALL** |

Total bars: 7,861,440

**Actual throughput: ~1 million bars/second**

**Note:** The infrastructure seems now ok to start building API 1.1 and replay (market simulation).

**Note:** DuckDB with Numpy memory-mapped views is a `golden technology`. Replay is going to flyyyy.

## Notice: HTTP service

[HTTP API](http.md) service is implemented. It follows more or less the same syntax as the builder component. You can also define your own HTML pages, eg to render charts. Example is added to the ```config/dukascopy/http-docs``` directory.

![Example](../images/webservice-example.png)

You can now visually compare your data, example SGD:

![SGD](../images/visual-compare-sgd.png)

## Notice: Panama backadjustment "Public beta" live

**Update:** Assuming the rollover values from the broker are correct, this is acceptable. I checked one year of BRENT data. In some cases, a gap remains because applying the broker-specified adjustment can leave a gap—October 2025 is an example—whereas November and September are superbly corrected. You can verify the rollover values in your ```data/rollover``` folder; those are the values being used. I still need to check it against an other datasource with continuous prices. eg to confirm the October one. If that one checks out, i will remove the "beta status".

I’ve implemented an initial version of the Panama backadjustment logic. It’s now available for you to try, although I’m still rigorously testing it myself. At the moment, rollover adjustments are supported for *-USD commodities, *-USX soft-commodities and *TR* bonds. I have tested it with:

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

## Notice: What about MT5?

There will be some exploratory research in January. Low priority.

## Notice: What about realtime? Second-level updates

Engine is capable of this. Creating a second-level aggregate file and then calling the incremental cascade every second. The resampling cascade (binary version), on a single-core, is able to push 20 years of EUR-USD data to 10 timeframes in just over 2 seconds. Speed is there. Incrementality is there. 

Hard number: 7844920 candles in 2.5 seconds = ~ 3 million candles/second

Why is it not there? Beyond scope of what i need this for atm. Perhaps in future version.

## Hall of Fame

List of the most "interesting stuff" encountered, during development of this project

**ASX is record holder**
- Monday-specific EPOCH-based candles only during day-session - resolved
- H4 candles spanning 6h10m - resolved
- 2020 severe DST/STD switch issues MT4-side \
  **The decision is:** We are going to replicate the (bug-) behavior through date-range bound, custom,  timeshift support in transform. There are changes for leap-years needed anyhow. The two complement each other.
- Sub-hourly intraday candle offsets at HH:51 and HH:10 - resolved

**SGD**
- Only in winter merge of a 11:51 candle, not in summer, while similar behavior - resolved
- Similarly to ASX, sub-hourly intraday candle at HH:51 - resolved

**MT4 general**
- Leap-year only lag of STD switch - unresolved (will solve in boundaries logic)
- Interesting DST/STD switch logic, based on NY DST state either GMT+2/GMT+3 - resolved
- 4x DST/STD annual switches per timezone-dependent asset - resolved

**Performance**
- Unexpected very high performance of Python in binary mode.

**AI**
- AI CANNOT be used for complex logic - it hallucinates and fails on edge cases
- AI CAN be used for docstring and inline commenting of code - it excels at that
- AI CAN be used for QA purposes - it actually found a bug that really mattered
- AI CAN be used for generic HTML and Javascript implementations - it excels at that
- AI CAN be really funny - especially Grok!

I think the solution came out really really well.

"In the intricate tapestry of apparent chaos, true mastery lies not in imposing order upon the unknown, but in patiently decoding its hidden patterns—until one day, with quiet revelation, we declare: the enigma is unveiled, and what was once obscure now illuminates the path for all."

Wishing you all a highly profitable 2026! 🚀









