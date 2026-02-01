

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

**Performance update coming**

Beta/0.6.7 was updated with the performance fixes. Documentation indicators.md and external.md got updated as well to reflect the new hybrid-indicator situation. I am still testing it.

Want to try out the beta?

```sh
git fetch -p
git checkout beta/0.6.7
# to install polars dependency:
pip install -r requirements.txt
```

Should be non-breaking. Also, when developing indicators in an own repo, see bottom of that indicators.md file in beta/0.6.7 branch.

**Note:** This is a 12.5x performance gain. Just checked the main branch vs the beta branch.

Original main branch: 7,796 ms (7.8 seconds)
Beta/0.6.7 branch:   622 ms (0.62 seconds)
Context: 1 mln rows x 55 indicators
API: get_data [internal API](external.md)

The price-only API is completely ridiculous: >13 million records per second.

Load-test came-out fine. Tested with 1 billion rows. Repeated calls. No troubles there. Maximum parameters are about 160000 rows (60k warmup) with 3500 indicators. Very wide column query. Beyond that, my memory wont allow and i get OOP's.

Profiling shows that about 90 percent of time is now in the high-performance Polars rust-engine.

```sh
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        9    0.083    0.009   >14.406<    1.601 ../util/api.py:102(get_data)
        9    0.028    0.003   13.534    1.504 ../util/parallel.py:521(parallel_indicators)
        9    0.063    0.007   13.506    1.501 ../util/parallel.py:144(compute)
       54    0.000    0.000   12.795    0.237 ../site-packages/polars/lazyframe/frame.py:1821(collect)
       54   12.793    0.237   >12.793<    0.237 {method 'collect' of 'builtins.PyLazyFrame' objects}
```

[Performance doc](performance.md)

What this project proves is that Memory Mapped IO is actually a superior technological choice for ordered append-only timeseries data. The project doesnt even have the correct binary format (yet). Yet, it is already pushing way beyond the 13 million rows/second-actually doing around 18 million on my laptop-for the price-only API, using Python. With the correct binary format and storage-type-which is reserved for the "next-gen"-this pushes easily in the 30-60 million/sec range.

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





