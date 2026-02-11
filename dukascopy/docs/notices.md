Market research- and analysis tool, feature-engineering, but you can do so much more with it, if you are a bit "handy".

Tomorrow is another massive-sprint day. I will have a go at panama. Panama and stock split are nothing more than applying an (optionally aggregated) correctional value to prices for a range of timestamps, either being a `-`, `+`, `*` or a `/`.

- `-` subtract (e.g. cash dividend adjustment)
- `+` add (rare, e.g. some special distributions)
- `*` multiply (stock split ratio, reverse split)
- `/` divide (rare, e.g. some spin-off value adjustments)

Expect it to be done tomorrow and to land Friday or latest Saturday.

## **Notice: Web-interface small issue**

No. This was the RSI indicator. To reach 99.9% convergence (where the floating-point difference is negligible), you generally need about 10 to 15 times the RSI period.

It was 3 * rsi_period. Made it 15. Now all oke.

## **Notice: Numba JIT optimizations**

Impressive performance optimizations on shannonentropy, marketprofile, volumeprofile and psar using numba JIT. Really impressive. See [here](numba.md) on how to optimize indicators that contain for-loops.

```sh
✅ OK    | psar                      |       0.67 | Polars Expr     | util | Previous: 15ms+
⚠️ SLOW  | marketprofile             |      13.35 | Polars Expr     | util | Previous: 500ms+
✅ OK    | shannonentropy            |       3.72 | Polars Expr     | util | Previous: 900ms+
⚠️ SLOW  | volumeprofile             |      31.58 | Polars Expr     | util | Previous: 500ms+
```

Note: you will need to install numba dependency: `pip install -r requirements.txt`

I am trying to build a "performance-first"-culture around this tool. Performance "enables". 

Before: Try a new indicator idea → Wait 30 minutes for backtest → Lose focus → Abandon idea

Now: Try idea → 1.2 seconds → See results → Refine → Try again → Stay in flow state

I have been around long enough to know that performance is a first-class citizin for tools like these.

How long? since 2009,...

Funny songs (something different for a moment, nostalgia):

- https://www.youtube.com/watch?v=K2ku1A5Ox8U&list=RDK2ku1A5Ox8U (mount gox debacle, what latency can do)
- https://www.youtube.com/watch?v=YGGzinyB1TI&list=RDYGGzinyB1TI (crypto pumps, wolong)

Also have a solution to the GIL locking. Python 3.14t. But it is currently too unstable for the dependencies. Dependency wheels are not updated for 3.14 yet. So we wait.

Will this become realtime? Short answer: yes. When? Within 6 months. There are some specific things that need to be done to make it realtime capable. The split-up and the seperate feeder with arrow flight is part of the solution. There will be a complete rewrite of the ingestion part.

## **HTTP API now multi-process and export limit increased, get_data now thread-safe**

HTTP API is now multi-process when `reload:0`. You can specify the number of workers in `config.user.yaml` eg `http.workers:8`. This will spawn 8 worker processes distributed over 8 cores. Since we use memory-mapped files that rely on the OS page-cache-the processes share this cache- memory usage will remain limited. Concurrency issues are now solved. `reload:1` means development mode == 1 worker.

Limit: You can now export up to 1 million rows from the HTTP-API-export view function-as CSV. With indicators.

Thread-safety: MarketDataCache is now thread-safe. It is now safe(r) to call get_data and get_data_auto from threads.

Latest mainbranch also makes it easier to customize line-colors for your custom indicators. After `git pull`, run `./setup-dukascopy.sh`. Read the [templates.md](templates.md) file (bottom) for the how-to.

~~**Important:** only export 1 million rows with fast indicators. Don't export 1 million rows with either shannonentropy, market profile and volume profile. It works with these but you will be waiting literally "ages". When you need 1 million rows, programmatically, don't use the HTTP-API, use the [bootstrap](external.md) approach. HTTP API is purposed for monitoring/charting/low-friction exports.~~

^^ After optimizing market profile and volume profile, you can safely export 1 million rows with these. The download starts after about 3 seconds. 

But... When you need 1 million rows, programmatically, don't use the HTTP-API, use the [bootstrap](external.md) approach. HTTP API is purposed for monitoring/charting/low-friction exports.

A high-speed TCP [Apache Arrow Flight](https://arrow.apache.org/docs/format/Flight.html) service will get implemented to support distributed processing. 

Performance differences (concurrency: 64):

```sh

http.workers: 1, http.reload:0
🚀 Starting Load Test: 1000 requests, 64 concurrent...

==============================
🏁 TEST COMPLETE
Total Time:     16.31s
Requests/sec:   61.30
Avg Latency:    1015.40ms
Status Codes:   {200: 1000}
Errors:         0
==============================

http:workers: 16, http.reload:0
🚀 Starting Load Test: 1000 requests, 64 concurrent...

==============================
🏁 TEST COMPLETE
Total Time:     2.94s
Requests/sec:   339.98
Avg Latency:    175.25ms
Status Codes:   {200: 1000}
Errors:         0
==============================
```

Conclusion: increase from 1 worker to 16 workers, increases throughput from 61 req/s to 340 req/s (20,400 requests per minute).

I have added the `http_loadtest.py` to the examples directory-it uses the BTC-USD symbol and standard indicators.

By leaning on the OS page cache for memory-mapped files, this is essentially a lock-free, shared-memory data bus that allows 16 workers to hammer the same dataset without the usual RAM overhead or synchronization bottlenecks.

## **BUG!**

Today, 2026-02-09T1730+0100, i found a bug while i was working with CSV data for trading. I use this stuff myself too, meaning automatically that deeper integration tests are being performed. I found out that mixing pandas indicators with polars dataframe indicators, somehow got broken. I have fixed this.

You will need to update.

## **Replay mockup is back**

I have re-inserted the "bit scroll-glitchy" replay mockup for demonstration purposes. You can use it to simulate market replay. It can be handy for certain purposes-eg examining custom-indicator-crosses. Its just a mockup but works with all your symbols, timeframes and indicators. I will leave it in. Copy over the `config/dukascopy/http-docs/replay-mockup.html` to your `config.user/dukascopy/http-docs/replay-mockup.html` if you want to "(re)play with it".

After copying `http://localhost:8000/replay-mockup.html`

PS: this is a "chart player or playback", not a real replay. The real one will have partial bar building etc. But that is for later. Core needs to be great first.

## **HTTP-STATUS 400 is now "transient"**

I forgot to mention but this was implemented already a "few" commits back. Status-code 400 is now transient. That means when the ingestion encounters a 400 state, it will retry. This makes ingestion a bit more robust. Play with the number of `retries`, `jitter`, the `backoff_factor` and the `timeout` if you are having issues syncing up. Don't overdo it on the `rate_limit_rps` setting though.

Preliminary conclusion, since 3 weekends in a row: 400 errors? it's likely maintenance. When you are in-sync and somehow use this for 24/7 trading purposes, monitor your BTC-1m-candles closely (in the weekend). I will provide that `is-stale` counter-part to `is-open` soon.

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

**Update:** The is-stale functionality will compare last BTC 1m tick with the system-time one time and store an offset-file which updates once a day. Or something similar. This determines the local systems time-offset compared to the server (no need for a fixed configuration). It will store it somewhere and the argument being passed to is-stale (tolerance, needs to know how frequent you update) will be used to detect stale-ness. So the solution is known. Kinda busy today... but it will be here soon.
