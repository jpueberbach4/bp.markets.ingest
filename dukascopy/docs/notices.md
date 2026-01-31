

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

**New performance update coming**

I’ve reached the theoretical performance limits of my hardware for the internal API training calls. Processing 1 million rows with 500, different period, SMA (eg ..,sma_2500) indicators now completes in under 2 seconds, ~280 million calculations/second. I’m currently cleaning up the code and testing the update. It took a full day of profiling and tuning to get to this point.

Beta/0.6.7 was updated with the performance fixes. Documentation indicators.md and external.md got updated as well to reflect the new hybrid-indicator situation. I am still testing it. It seems oke but needs some heavy duty load testing. Tomorrow.

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


