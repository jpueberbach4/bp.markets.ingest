
## **WSL Fast-API issue - `--reload` consumes one core**

This is known to me. I had a go at it but took too much time to solve quickly. Tried watchfiles, watchdog, exclusions, inclusions. Everything. The problem is that, under WSL2, the inotify is broken. So when a file changes, the inotification is not being raised. FastAPI/UVLOOP with `--reload` detects that it is not working and instead goes in a loop mode. This causes the CPU-issue. Since the root has many files (cache, data,..).

If you really find it annoying, you can disable in `api/run.py` reload=True and set it to False. It's annoying. It spins up my fans too. However, when setting to False, it wont detect indicator `additions`. When you set it to false, you will need to keep setting it to False or do some git stash/pop tricks when updating, git pull. 

The issue has pretty low priority given the list, spent an hour on it already. That's too much for this problem at this moment.

I added it to the list (if can't find solution soon, i will make it configurable in `config.user.yaml`).

**Update:** It is now configurable in the `config.user.yaml`. `http.reload:0` = do not watch files, no cpu-loop under WSL2 (production setting). `http.reload:1` watches files for changes and immediately adds new indicators to the interface (after pressing update view) as you add them (development setting).

## **Fix for the open-candle problem - NEEDS BTC-USD as HEARTBEAT symbol**

We have a temporary solution for the "open-candle" problem. Eg mark the open-candle in the output `is-open:1` or `is-open:0`. However, this requires you to configure the symbol `BTC-USD` and have it synced up. The `BTC-USD` symbol acts as the heartbeat of the market. 

An indicator `is-open` was added to the internal system indicators. You can query it in your webinterface or subquery it using `get_data` by passing `is-open` as an indicator.

This is a temporary but ROBUST solution when you can update at least `ONCE EVERY TWO HOURS`. So for live connections this works where update-time is < 2 hours. Eg your crontab setting is once-every-two-hours. You get the point.

Another robustness update is coming for the "cabin in the woods but no internet"-problem.

You can checkout the indicator [here](../util/plugins/indicators/is-open.py).

**Note:** When you have `custom timeframes` defined, copy over the `is-open.py` indicator to your `config.user/plugins/indicators` directory and add your `custom timeframe` to this block. The user-defined indicator will overrule the system-one (yes, conflicting with the indicator.md documentation, will change that documentation soon).

```python
        # Around +- line 120
        # Duration (in ms) of each supported timeframe
        tf_lengths = {
            "1m": 0,
            "5m": 300000,
            "15m": 900000,
            "30m": 1800000,
            "1h": 3600000,
            "2h": 7200000, # custom 2-hourly timeframe example
            "4h": 14400000,
            "1d": 86400000,
            "1W": 604800000,
        }
```


## **Another performance update**

This one hits your indicators. You can now optionally accept a polars Dataframe inside of your plugin. You need to set `meta.polars_input` to 1. The calling function then passes in a polars dataframe. You can then either return a pandas dataframe or a polars dataframe. Generic advice is to prevent conversions as much as possible. So polars input has the preference. 

Gain? For 1000 records on a complex recursive indicator: 51ms to 19ms. 60000 records from 100ms to 37ms. See the [indicators](indicators.md) doc.

So my statement that it couldnt be pushed further was wrong-at least for "calculate"-indicators.

Recursive calls got a lot cheaper.

The HTTP-API is still on Pandas. It will be sped up too by switching it to return_polars=True. So the HTTP Wall time includes a conversion-overhead from polars to pandas. This is why it might feel that the latest performance fix actually does nothing, on the web-interface.

The truth is (internal optimized get_data call), with complex indicator: 1000000 records, time-passed: 92.94088200840633 ms + 1 indicators (which subqueries both H4 and D1 frame RSI). I have added the HTTP-API fix to the todo list.

## **Next**

Hardening, quality. Then. Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer.
