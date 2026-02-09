## **HTTP-API now Polars-native**

HTTP-API is now polars native. When querying with polars:1 indicators -> blazing. Good update.

## **HTTP-STATUS 400 is now "transient"**

I forgot to mention but this was implemented already a "few" commits back. Status-code 400 is now transient. That means when the ingestion encounters a 400 state, it will retry. This makes ingestion a bit more robust. Play with the number of retries, the backoff factor and the timeout if you are having issues syncing up. Don't overdo it on the rps setting though.

**Note:** My settings:

```yaml
# Below you will find the configuration for the download.py script. 
download:
  max_retries: 10                     # Number of retries before downloader raises
  backoff_factor: 1.2                 # Exponential backoff factor (wait time)
  timeout: 10                         # Request timeout
  rate_limit_rps: 1                   # Protect end-point (number of cores * rps = requests/second)
  mode: http2                         # DownloadWorker-type: requests or http2
  jitter: 5.0                         # Add a random jitter up to this amount (seconds)
  paths:
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
```

(these are working settings for people that are in-sync)

PS. it are actually status 500 errors, masked as a 400. Don't know for sure it's a rate-limit. I checked again, doesnt look/feel like rate-limiting. This is something that needs to get solved professionally, later. This software is not yet far enough developed to actively start exploring options. Perhaps, i should change the priorization of todo items and first makes this "locally complete". Good night.

You should position this as a market research- and prototyping-tool. 

## **WSL Fast-API issue - `--reload` consumes one core**

I had a go at it but took too much time to solve quickly. Tried watchfiles, watchdog, exclusions, inclusions. Everything. The problem is that, under WSL2, the inotify is broken. So when a file changes, the inotification is not being raised. FastAPI/UVLOOP with `--reload` detects that it is not working and instead goes in a loop mode. This causes the CPU-issue. Since the root has many files (cache, data,..).

**Update:** It is now configurable in the `config.user.yaml`. `http.reload:0` = do not watch files, no cpu-loop under WSL2 (production setting). `http.reload:1` watches files for changes and immediately adds new indicators to the interface (after pressing update view) as you add them (development setting).

Note: changes to existing indicators are detected when `http.reload:0`. 

## **Fix for the open-candle problem - NEEDS BTC-USD as HEARTBEAT symbol**

We have a temporary solution for the "open-candle" problem. Eg mark the open-candle in the output `is-open:1` or `is-open:0`. However, this requires you to configure the symbol `BTC-USD` and have it synced up. The `BTC-USD` symbol acts as the heartbeat of the market. 

Configure the `BTC-USD` symbol as last symbol in your `symbol.user.txt` to ensure maximum reliability.

The indicator `is-open` was added to the internal system indicators. You can query it in your webinterface or subquery it using `get_data` by passing `is-open` as an indicator.

This is a temporary but ROBUST solution when you can update at least `ONCE EVERY TWO HOURS`. So for live connections this works where update-time is < 2 hours. Eg your crontab setting is once-every-two-hours. You get the point.

Another robustness update is coming for the "cabin in the woods but no internet"-problem (is-stale:1 or 0). This solution will also cover warning for system outages. One of the points on the todo list. Warn user for data-source outages.

You can checkout the indicator [here](../util/plugins/indicators/is-open.py).

**Update:** This approach works really well, and its simplicity stems from the system's design. The fail-fast principle plays a key role: if even one symbol’s download fails, the process fails immediately—preventing updates for any symbol.

When all downloads succeed, and BTC-USD has new data, it serves as the reference point. If BTC-USD has new data but GBP-USD does not, this indicates that the GBP-USD market is closed.

We can then take the last minute of BTC-USD data and subtract the timespan of the last candle (e.g., 4 hours). If the result is later than the start time of that last candle, the candle is considered closed.

This method is symbol-agnostic and automatically handles market closures, holidays, and similar scenarios

## **Next**

Hardening, quality. Then. Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer.
