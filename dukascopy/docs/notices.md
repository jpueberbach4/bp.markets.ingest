**TA-lib tested indicators**

In order to ensure quality I have tested some indicators against TA-lib, implemented through a unit-test. Users having Python ta-lib installed will be able to run the test. When TA-lib is not installed the unit-test will skip.

These have been checked and are-now-compliant to TA-lib:

- ADX
- AROON
- ATR
- ATRP
- BBANDS
- CCI
- CHAIKIN
- CMO
- EMA
- EOM
- MACD
- MIDPOINT
- MFI
- OBV
- PSAR
- ROC
- RSI
- SMA
- STOCHASTIC
- STDDEV
- UO
- WILLIAMSR


I will dig the TA-lib deeper in order to see if we can compare more. Eg if there are more goodies in there. Probably. TA-lib has 150 indicators. So expect the test to get expanded.

**Note:** It can be "a bit difficult" (under WSL2) to install ta-lib for Python. https://pypi.org/project/TA-Lib/

**Note:** For now I will leave it at this. Friday we continue.

**Good practice advice when you are building your own indicators**

Since there is currently no "run-time" protection for recursion loops caused by custom indicators, i have added a unit-test which does the checking for recursivity loops. This is a V1 version of the recursion guard, a V2 is coming. The V1 version does not yet take the indicator options into account. Eg first loop you call test-sma_20 and second recursive call you call test-sma_50... this is currently caught as an unlimited loop call when calling with same timeframe and symbol. 

How to test your indicators? Simple. Just run `./run-tests.sh` regularly when developing complex recursive indicators.

Eg this is covered now: 

```python
# this indicator name = test-sma, we call it with EUR-USD/1m
def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Simple Moving Average (SMA).
    """
    # This will error after the second recursive call 1m->5m->5m->error
    df = get_data( \
        timeframe="5m", symbol="EUR-USD", \
        after_ms=0, until_ms=132896743634786, limit=1000, \
        indicators=['test-sma'] \
    )

    # This will error after first call 1m->1m->error
    df = get_data_auto(df, indicators=['test-sma'])

    ...

```

Hope this helps a bit to keep your indicator/feature stack and the engine a bit safe.

**19 new indicators**

19 new indicators were added. These were "quick-wins".

- **Fast Indicators**: Most use pure Polars vectorization
- **Recursive Indicators**: McGinley, Kalman, SuperTrend use Python loops
- **Heavy Indicators**: Volume/Market Profile use O(n²) histograms

I will have another quality pass on them soon.

**Performance fixes**

Performance fixes have been applied. Update entails:

- Hybrid Polars/Pandas indicator engine
- Native Polars dataframe support from get_data API
- All system indicators have been converted
- Performance +12.5x on 1 million with 55 indicators. Polars only indicators. With return_polars=True ~520ms.
- Performance +8-10x on 1 million with 55 indicators. Mix of high perf hybrids. Without return_polars=True ~730ms.
- Cleaning up here and there.

Profiling showed that >90 percent of time is now going to Polars high-perf rust engine.

I think we have now maxed out what is possible for this stack. There was one more performance update added. Batched execution of Polars expressions (to prevent graph explosion on very wide column data) plus we keep the original fp64 precision intact (no rounding). Rounding is now up to the caller's discretion. Some may need 4 decimals, others 8, fixed rounding at 6 inside the engine was a bad idea anyhow.

I tried the most crazy configurations you can think of and profiled them all. I can't find anything more to tune. This should be the solid performance-base to build the rest on-top. I calculated that it's achieving over 4GB/s in memory bandwidth. That's really impressive for a laptop ryzen 7 nvme combo.

Have a great day.

Current Laptop: ~4.7 GB/s (Impressive).

Ryzen 9 9950X: ~14 GB/s (AVX-512 is the game changer, testing with this setup soon).

Threadripper: ~25 GB/s (Unlocks "Wide" datasets with 10k+ columns).

CPU is maximally saturated at 80 percent. Higher is not possible since the FPU units are fully allocated. I have 16 threads but "only" 8 FPU's. 2 threads share one FPU. So when one thread is using a FPU for 100 percent, the other thread is in wait state, idle. This gives the "illusion" we are not maxing out the cores. There is a term for this SMT-wait/SMT-contention/Execution unit saturation. 

**Next**

Hardening, quality. Then. Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer.

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

Update: I’ve been in contact with Dukascopy, and they’ve confirmed that the technical hiccups were on their side—they’ve since been fixed. Carry on was the message i read from it.




