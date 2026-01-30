

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

**New performance update coming**

I’ve reached the theoretical performance limits of my hardware for the internal API training calls. Processing 1 million rows with 500, different period, SMA (eg ..,sma_2500) indicators now completes in under 2 seconds, ~280 million calculations/second. I’m currently cleaning up the code and testing the update. It took a full day of profiling and tuning to get to this point.

**Less codechanges**

Performance example, EUR-USD 1m data, random 2025 data, 5 indicators.

```sh
100 records, time-passed: 30.578309088014066 ms (this is with one-time plugin load)  + 5 indicators
1.000 records, time-passed: 28.57433701865375 ms + 5 indicators
10.000 records, time-passed: 37.17033995781094 ms + 5 indicators
100.000 records, time-passed: 129.57307707984 ms + 5 indicators
```

Sub-lineair scaling. To compare: For 100,000 rows, TimescaleDB will take 500ms to 2 seconds to return the data and calculate indicators. This does it in 0.12 seconds.

~~I will put the last critical fix in tomorrow-make the internal API usable from external code.~~ Its available in main. See [here](external.md).

Now i go rest again. I have the flu. But a promise is a promise. Delivered.

**Status: slower endpoint**

The endpoint appears to be rate-limited, which is likely a consequence of the recent outages on the Jetta endpoint. As a result, a full sync from scratch may require some patience.

If you are already in sync, you’re in luck. If not, be prepared for a slower process—sometimes you may need to restart ./rebuild-full.sh a few times before it completes successfully.

This software is still in active development, and at this stage high-speed data feeds are not a requirement (at least for my use case). Once the system is stable, I’ll reach out to Dukascopy to explore options for paid or higher-throughput feeds.

**Status: bottom sniper**

I am currently developing an H4 bottom-sniper model using a 10-20 feature machine-learning setup.

The feature set includes, but is not limited to:

- Distance to a major D1 support zone, with confirmed historical buyer activity
- Higher-timeframe downtrend exhaustion (e.g. stair-stepping structure, flush-out candles)
- Volatility expansion 
- Distance to H4 liquidity, implemented in a manner similar to the support-distance feature
- Candle body size and wick structure
- Volume
- Price patterns
- Additional signals

The main challenges at the moment are technical, as most of the work involves translating discretionary chart “reading” into precise mathematical representations. What is visually intuitive for a human trader is significantly harder to encode in pure math.


Ofcourse there is the problem of overfitting. But... Let's see how far we get.

The system will get heavily tested as a feature engineering factory. Lets see how it holds up. 

It is possible or even likely that the above will spawn another round of updates. Efficiency updates etc. Will try to limit it to feature branches.


