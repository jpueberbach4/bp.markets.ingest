<u>MT4 is decoded.</u>

What's next?

- Replay/Market simulation
- Write-up

## **Notice:** charts and serial execution  

**Note:** Something i am considering atm is to take the project offline. It's all about P/L. Not about some fancy clone statistics. It will help on focus, if i go this way, the project will get relaunched when completely done. It prevents users from getting frustrated by bugs, the many commits etc etc. I will make a decision soon.

Will you completely take it offline or will there be some other repo, containing a locked, stable version? Yes. That is the plan. This one will dissapear, another, thoroughly tested repo, having below functionalities stabilized will be put up. However, there will be no maintenance on that stabilized product and it will be as-is. That project could be considered as a "stable data foundational layer with an API on top of it". And nothing more than that. So after the below round, a few days will be spend on unit-tests and stabilization. Then migrated.

Furthermore:

1. I have been looking into drawing functionalities. System will be upgraded to lightview charts + drawing extensions.

2. While developing my own indicators i noticed i often was reliant on similar calculations performed by existing indicators. SMA's, RSI etc. I had to copy over the logic to my custom indicators. This is weird. So i came up with a solution. `?executionmode=serial`. This is not yet implemented but will be implemented soon. Basically pipelining inside of your HTTP request will get supported. See http.md for more information. This weekend it will be done. I have an indicator file of nearly 10KB. Thats no good. Fixing. \
\
Something like this will be implemented (multi-core processing of indicators is coming-i had a breakthrough):
```yaml
risk_on:
  indicators:
  - parallel: [ema(21), ema(55)]          # expliciet parallel groep
  - parallel: [rsi(14), stoch(14,3,3)]
  - supertrend(10,3)
  - my_risk_on_entry
  prune:
  - ema_21
  - ema_55
  - supertrend_10_3
```

**Note:** Cascading will be supported here as well. Basically you can build a `tree`.

3. There will be another round of robustness/cleanup/quality operations. This time it will involve the HTTP API. Will be non-breaking. Also an abstraction will be added to easier access data from other symbols and timeframes. Currently i am using API calls but this is overhead, we can go direct as well. The direct mmap approach. Query/Dataframe in, DataFrame out. Eliminating HTTP overhead. So an internal API layer will be added which the indicators can use.

```python
us10y_df = bp.get_data('USTBOND.TR-USD', '1h', current_ts - 86400000, current_ts, ['rsi_14'], options)
```

I am still optimizing this. Trying, testing, encountering bottleneck -> think -> solution -> implement -> reiterate. This is definately not finished yet.

What am I using this system for? A background process that deeply analyses incoming 1h "ticks". Generates signals, those get exported, read and paper-traded atm. Signals and results get compared. 

## **Notice:** Functional replay mockup - 2025-01-19

For demonstration purposes, I’ve included a fully functional replay mockup in this repository. You can use it to run replays with your own assets, indicators, and configurations.

This is not the definitive replay implementation—the final version is significantly more advanced than what’s included here.

That said, feel free to explore and experiment with it. Since this was implemented and reviewed quickly, there may be minor glitches or rough edges.

![Mockup](../images/replay_mockup.gif)

The url and the script. `config/dukascopy/http-docs/replay.html`, copy it to `config.user/dukascopy/http-docs/`. After copying `http://localhost:8000/replay.html`. You will find a `Jump/Replay` button on the right topside.

**Note:** This is just a basic candlestick replay. It’s meant to show what can be built on top of it and to spark some imagination about what’s possible—and what’s coming next. What is interesting to mention is that all data-points you see are server-side generated. Not on the browser-side. So everything you can render on the chart is also queryable through the API.

## **Notice:** Interface (bug-)fixes - 2025-01-19

**Note:** I updated the index.html **twice** today. Now its oke. I think. I hope. Update view works too. These are important changes in case developing custom indicators. When you press update view, you want to see the new indicators output immediately, without a shifting chart or any other "weird stuff". All that has been fixed. My JS skills are improving.

Copy over the new `config/dukascopy/http-docs/index.html` to your `config.user/dukascopy/http-docs/index.html`.
