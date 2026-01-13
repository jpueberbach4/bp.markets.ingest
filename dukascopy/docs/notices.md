<u>MT4 is decoded.</u>

What’s next?

- Indicator support in selectors \
Implemented in a manner consistent with existing modifiers—symbol-wide by default, with timeframe-specific overrides.

- Builder upgrade and HTTP API upgrade to v1.1 \
Introducing indicator-integrated outputs.

- Feature-rich market simulation \
Full high-performance replay functionality.

**Note:** Added a small utility for "the less technical users" among us. Update and then copy over `config/dukascopy/http-docs/indicator.html` to your `config.user/dukascopy/http-docs` directory. Then open `http://localhost:8000/indicator.html`. It allows you to get your data more easily (as CSV).

**Note:** Now that we are on binary mode, i have updated the API record-limit to 5000. So you can get 5000 minutes, ... 5000 days etc. In one call.

**Note:** How on earth is this so fast, on a laptop? We are leveraging the OS page cache and CPU cache. OS does all the work. CPU gets fed in the right way. We could potentially notch it up even more, using GPU's. Currently, my system is saturated on IO-the NVMe. So locally, on my system, a GPU implementation is not beneficial. Only those with NVMe arrays would benefit. Not many indie traders have raid NVMe. Perhaps in the cloud, but not at home.

**Note:** Expect v1.1 to land, latest Wednesday.

**Update:** I’ve been working on integrated indicator support. I wasn’t satisfied with the performance in version 1.1, so I decided to remove DuckDB and take a different approach using direct NumPy computations. It’s still heavily under tuning, but the screenshot below shows what you can expect. On Wednesday, I’ll be spending the entire day building an HTML overlay that will allow you to apply indicators directly. We currently have around 40 indicators available, but I’ll focus on supporting those that can be plotted on charts or are most commonly used (SMA, EMA, RSI, MACD, etc. — essentially the top 10).

![Example indicator integration](../images/integration_test1.png)

**Note:** API v1.0 will be faster than v1.1 when indicators are included in the query, which is expected due to the additional computations involved. Indicator calculations are performed in parallel, and overall performance remains solid. With three indicators added to a 1-minute chart, response times stay under 80 ms. API v1.0 will remain supported.

```sh
{
  "status": "ok",
  "options": {
    "select_data": [
      [
        "EUR-USD",
        "1m",
        "data/aggregate/1m/EUR-USD.bin",
        [],
        [
          "sma_10",
          "sma_50",
          "sma_200"
        ]
      ]
    ],
    "after": "2025-02-01 00:00:00",
    "until": "3000-01-01 00:00:00",
    "output_type": "JSON",
    "mt4": null,
    "limit": 1440,
    "offset": 0,
    "order": "desc",
    "callback": "__bp_callback",
    "fmode": "binary",
    "count": 1440,
    "wall": 0.0485472679138184
  },
  "result": [
    {
      "symbol": "EUR-USD",
      "timeframe": "1m",
      "time": "2026-01-13 11:54:00",
      "sort_key": 1768305240000,
      "open": 1.16707,
      "high": 1.16707,
      "low": 1.16698,
      "close": 1.16699,
      "volume": 115.65,
      "year": "2026",
      "indicators": {
        "sma_10": 1.16699,
        "sma_200": 1.1663,
        "sma_50": 1.16682
      }
    },
    ...
```

This is the MAXIMUM performance, with profiler disabled. 3 indicators, sma20/50/100 on EURUSD 1m chart. Single asset-in query.

Why i removed DuckDB? When the tail updates or changes, i need to refresh a complete mmap view. Now, i am able to just update the tail. I still need to create this part.

## Notice: API 1.0 is now locked - 2026-01-12

API Version 1.0 is now locked and can be considered stable. It will not change in URL syntax, functionality. Only critical bugfixes-also when encountered in indicators-will be fixed. API 1.1 will become the new version. 1.0 will remain supported, indefinately. You can build on it safely.

PS: will there be more indicators added to 1.0? If 1.1 gets more indicators, 1.0 will get more indicators. The main difference between API 1.1 and API 1.0 are its selection syntax-you can specify indicators per timeframe and/or symbol in the DSL- and its internal handling of the warmup rows. 1.1 just selects more rows for the warmup, then pushes it through the existing indicators logic-multithreaded, then merges and just before output it drops the warmup rows. These are the main differences. The indicators are compatible between 1.0 and 1.1, hence it's easy to "backport" new indicators to 1.0.

## Announcement: deprecation of the CSV format - 2026-01-10

The CSV format is now in a deprecated state. CSV will continue to be supported until the release of version 0.7, but new features—such as replay—will not support CSV. This is because CSV lacks the performance required for high-speed processing.

The default CSV reader and writer will remain available for existing features. If you do not require the new functionality, you can safely ignore this notice and continue using the current version (tag 0.6.5).

The builder component, of course, will continue to support CSV and Parquet generation. This also means that the newly proposed selection syntax, including indicator generation support, will be compatible with CSV.

[Replay](https://github.com/jpueberbach4/bp.markets.ingest/blob/feature/021-replay/dukascopy/docs/replay.md)

**Note**: I want to re-emphasize that all of this was, likely, impossible without [Dukascopy](http://www.dukascopy.com) free and open API's. If you find this tool useful, consider trying their platform.

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
- 40+ indicators
- 2 UI, 1 for charts, 1 to build queries

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









