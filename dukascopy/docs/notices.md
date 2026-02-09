## **HTTP-API now Polars-native**

HTTP-API is now polars native. When querying with polars:1 indicators -> blazing. Good update.

## **HTTP-STATUS 400 is now "transient"**

I forgot to mention but this was implemented already a "few" commits back. Status-code 400 is now transient. That means when the ingestion encounters a 400 state, it will retry. This makes ingestion a bit more robust. Play with the number of retries, the backoff factor and the timeout if you are having issues syncing up. Don't overdo it on the rps setting though.

Preliminary conclusion, since 3 weekends in a row: 400 errors? it's maintenance. When you are in-sync and somehow use this for 24/7 trading purposes, monitor your BTC-1m-candles closely (in the weekend). I will provide that `is-stale` counter-part to `is-open` soon.

## **WSL Fast-API issue - `--reload` consumes one core**

I had a go at it but took too much time to solve quickly. Tried watchfiles, watchdog, exclusions, inclusions. Everything. The problem is that, under WSL2, the inotify is broken. So when a file changes, the inotification is not being raised. FastAPI/UVLOOP with `--reload` detects that it is not working and instead goes in a loop mode. This causes the CPU-issue. Since the root has many files (cache, data,..).

**Update:** It is now configurable in the `config.user.yaml`. `http.reload:0` = do not watch files, no cpu-loop under WSL2 (production setting). `http.reload:1` watches files for changes and immediately adds new indicators to the interface (after pressing update view) as you add them (development setting).

Note: changes to existing indicators are detected when `http.reload:0`. 

## **Fix for the open-candle problem - NEEDS BTC-USD as HEARTBEAT symbol**

We have a solution for the "open-candle" problem. Eg mark the open-candle in the output `is-open:1` or `is-open:0`. However, this requires you to configure the symbol `BTC-USD` and have it synced up. The `BTC-USD` symbol acts as the heartbeat of the market. 

Configure the `BTC-USD` symbol as last symbol in your `symbol.user.txt` to ensure maximum reliability.

The indicator `is-open` was added to the internal system indicators. You can query it in your webinterface or subquery it using `get_data` by passing `is-open` as an indicator.

This is a ROBUST solution.

You can checkout the indicator [here](../util/plugins/indicators/is-open.py).

**Update:** This approach works really well, and its simplicity stems from the system's design. The fail-fast principle plays a key role: if even one symbol’s download fails, the process fails immediately—preventing updates for any symbol.

When all downloads succeed, and BTC-USD has new data, it serves as the reference point. If BTC-USD has new data but GBP-USD does not, this indicates that the GBP-USD market is closed.

We can then take the last minute of BTC-USD data and subtract the timespan of the last candle (e.g., 4 hours). If the result is later than the start time of that last candle, the candle is considered closed.

This method is symbol-agnostic and automatically handles market closures, holidays, and similar scenarios

**Update:** The cabin-in-the-woods-without-internet problem is a non-existent problem for `is-open`. We do not use the laptops `time()` anywhere. It only looks at the timestamps of the ingested candles. However, since we need to detect staleness-eg the dataprovider died on a market-we will introduce another indicator: `is-stale`. This indicator can be used to `safeguard` things. Soon.

## **Next**

Hardening, quality. Panama-data sidetrack. Then. Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer.

