Market research- and analysis tool, feature-engineering, but you can do so much more with it, if you are a bit "handy".

## **Is-open and timezones**

If you have something like this:

```yaml
Etc/UTC:                          # This is an example on how to resample assets using UTC
  offset_to_shift_map:            # Defines a map to shift based on offset minutes
    0: 0                          # No shift. Incoming data is already UTC. Warning: NO DASH!!
  symbols:
  # --- Stocks ---
  - AAPL.US-USD                   # OK
```

The is-open/drift functionality will not work properly. Why? 

The BTC-USD symbol is configured with GMT+2-atm. So the timezone GMT+2 and Etc/UTC differ by two hours, causing a drift of 120 minutes. Is-close will detect candles as closed. I will add support for this when `is-stale` also gets implemented. Normally, you want all symbols in one timezone, the timezone of the MT4 server or ALL in UTC. This issue affects only `advanced users` that have multiple timezone/asset combinations configured and only affect the symbols that are in a different timezone than BTC.

eg AAPL.US-USD in Etc/UTC and the BTC-USD in America/New_York -> AAPL has an issue.

I have updated the `AAPL.US-USD` symbol in `config/dukascopy/timezones/america-new_york.yaml` to `AAPL.US-USDX`.

## **Server kindness**

Re-iterating to be nice to the backend servers. After your initial sync, you can slow down your requests. Even when updating every minute (when you really need that). Implement a spreading/limit when in-sync.

Example config:

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

This will spread a sync for +/- 40 symbols over 30 seconds. More than enough time to stay "realtime", well within the 1 minute opportunity/sync window. You are lagging anyhow at minimum 1 minute compared to real realtime since the 1m candles are added when they are closed.


## **Side-tracking beta**

I have merged the sidetracking feature to the main-branch. This is without the config-builders, they are still being developed.

**Note:** There is only a sidetrack for BRENT-CMD.USD configured in the beta. You will need to add BRENT-CMD.USD to `symbols.user.txt`.

After updating with `git pull`, 

- Create a directory `config.user/dukascopy/sidetracking`
- Copy over the `config/dukascopy/sidetracking/BRENT-CMD.USD-PANAMA.yaml` to `config.user/dukascopy/sidetracking`

Next 

Open your `config.user.yaml`:

```yaml
# Below you will find the configuration for the transform.py script. 
transform:
  time_shift_ms: 7200000              # How many milliseconds should we shift (0=UTC, 7200000=GMT+2 (eg MT4 Dukascopy) )
  round_decimals: 8                   # Number of decimals to round OHLCV to
  fsync: false                        # Force flush to disk after each transformation
  fmode: binary                       # Only binary is supported from v0.6.6 onward
  validate: false                     # Force validation of OHLCV values
  paths:
    data: data/transform/1m           # Output directory for transform
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
  timezones:
    includes:
    - config.user/dukascopy/timezones/*.yaml
  symbols:
    includes:
    - config.user/dukascopy/processing.yaml
    - config.user/dukascopy/sidetracking/*.yaml # Un-comment/Add this to enable the BETA sidetracking feature for BRENT
```

Per symbol rebuilds are currently unsupported, so you will need to do a `rebuild-full.sh`.

## **Change in is-open**

There was a nasty bug in is-open. Because it is such an important feature, here is how it (now) works:

- let global_now_ms be the time_ms of the last 1m BTC-USD candle
- let tf be the currently selected timeframe (eg 4h)
- let tf_lengths be a dictionary that maps a tf to its length in ms (eg 1h = 3600000)
- let last_ms be the timestamp of the last candle of the currently selected asset and timeframe

Then, when:

**last_ms >= ( global_now_ms - tf_lengths.get(tf, 0))**

The last candle is considered **OPEN**, `is-open = TRUE`

Also, this means that when no data has arrived for some time on the selected asset, while data is flowing for BTC-USD, the selected last candle will be closed after the time-span of that candle has passed.

There will be two additional indicators:

- drift: will output how many minutes the 1m candle of the selected asset has drifted from the last 1m BTC-USD candle (available in main)
- is-stale(tolerance): will output if a market did not receive any data for the number of minutes specified by tolerance, relative to laptop-time.

**Broker Quirk Handling:** For timeframes less than 1 Day, if the asset's 1-minute drift is less than the timeframe duration, the system anchors the is-open boundary to the asset's own latest timestamp rather than the global heartbeat. This ensures non-standard candle lengths (e.g., SGD-IDX 6H30M "H4" candles) are correctly identified as open while the market is active.

See [config/dukascopy/timeframes/indices/SGD-indices.yaml](../config/dukascopy/timeframes/indices/SGD-indices.yaml) (merge logic).

**Note:** If your drift between assets is sometimes 1 minute, update your crontab - change the sleep value to 10:

```sh
*/5 * * * * sleep 10 && cd /home/jpueberb/repos2/bp.markets.ingest/dukascopy && ./run.sh
```

This gives the backend server a bit more time to synchronize all symbols.

Documented here (future reference): [Market-status indicators](market-status.md)

**Update:** I have updated the `config/dukascopy/http-docs/index.html` to show the drift value in the upper right corner of the web-interface. You need to copy `config/dukascopy/http-docs/index.html` and `config/dukascopy/http-docs/scripts/monitor.js` to their respective `config.user` directies.

## **Very cool tip**

For the coders under us. I just discovered something cool with AI. Just push your code in and say: annotate the code and mention complexity O(1), O(log N) and O(NxM) where applicable. It exactly pinpoints bottlenecks. It amazed me how helpful that actually is.

## **Panama and stocksplit**

Tomorrow is another massive-sprint day. I will have a go at panama. Panama and stock split are nothing more than applying an (optionally aggregated) correctional value to prices for a range of timestamps, either being a `-`, `+`, `*` or a `/`.

- `-` subtract (e.g. cash dividend adjustment)
- `+` add (rare, e.g. some special distributions)
- `*` multiply (stock split ratio, reverse split)
- `/` divide (rare, e.g. some spin-off value adjustments)

Expect it to be done tomorrow and to land Friday or latest Saturday.

Panama is nothing more than [this](../examples/BRENT-transform-panama.yaml) (example config).

**Update:** Panama is not an issue. Data is retrievable and is superb. For the rest, dividend-adjustments, corporate actions etc, I will make sure that the configuration layer is fine. Interfaces will get implemented with a tight-contract to provide for data-exchange between this tool and a third party resource. 

I have thought about building a repository for corporate actions, which can be auto-pulled to update your local enviroment, but there are two issues with this approach:

- 1st is a legal boundary (redistribution clause)
- 2nd is maintainability (it would put too much burden on me)

So correct strictly contracted interfaces implementation/support is the "mid-ground". An user can implement the interfaces to eg extract corporate action data from the SEC, Yahoo, CSV-files etc. Examples will be written but don't expect them to be ready before the weekend.

Futures rollover's will be completely solved, however. Stay tuned.

**Update:** Decision is final, this is how panama and corporate actions get supported. You can include config files in the transform step, defining post-processing rules. Eg, for BRENT-CMD.USD, pseudo-example:

```yaml
BRENT-CMD.USD-PANAMA:
  source: BRENT-CMD.USD
  post:
    volume-adjust:
      action: "*"
      columns: ["volume"]
      value: 34484
    panama-roll-01:
      action: "-"
      columns: ["open", "high", "low", "close"]
      value: 2.34 # Cumulative value, generated by the config builder
      from_date: "2026-01-25 00:00:00"
      to_date: "2026-02-12 23:59:59"
    panama-roll-02:
      action: "-"
      columns: ["open", "high", "low", "close"]
      value: 1.15
      from_date: "2026-02-13 00:00:00"
      to_date: "2026-03-15 23:59:59"
```

This will sidetrack a symbol named `BRENT-CMD.USD-PANAMA` using the source `BRENT-CMD.USD` with the post-processing steps defined. The configuration, for `future-contracts` will be automatically generated. Changes will be added to be able to only rebuild one specific symbol.

This is how it will work and it will support everything. The "config-builder" classes will define the "strict-contract" for config-generation.

You can even do: first prices * 2 then divide by 3 if needed. When resample is being rewritten, resample will also support post-processing to pre-generate indicators, so they don't have to be calculated at query-time and just can be pulled. This will give back the 15-30 million records/sec performance.

Some may argue that this is not only a panama, corporate actions update but actually a derivatives engine update.

**Update:** I have a first working implementation. Works great. Aggregation, resampling, everything works out of the box on this sidetracked data. Also the "live-appends" are working properly. 

I decided to launch this Saturday, to give me a tiny bit more time to make the interfaces optimal. See below screenshots, how much difference panama-adjusted data is:

Before:

![before](../images/brent.panama.before.png)

After:

![before](../images/brent.panama.after.png)

I am first writing for correctness and completeness, then a performance optimization pass will be performed.

**Note:** Negative prices are "normal" in backadjusted data for BRENT. So your backadjusted/adjusted data will run side-by-side with your live-broker data. I think this is the optimal strategy for handling this.

## **Security**

Oh yes! Security 🙈 Will get added too (especially flight). Security has been of "later concern" since this is a local-first private research tool that is supposed to run on a local-machine, tightly secured to 127.0.0.1. Clones, however, show that this is definately not only used on 127.0.0.1. 

I promise it will be taken care of when i rewrite the ingestion layer. If i will go as far as including a OAuth2 layer, i don't know yet. Needs to be lightweight. Performance-first.

TLS will be implemented as a minimum. Raw Public Key (RPK) Authentication will be implemented as a minimum.

## **Conversion pass to numba + polars expressions**

Numba has enabled us to move almost all indicators to pure Polars expressions. We still use map_batches. I am back to the drawing board for some indicators. Perhaps some will need to fallback to the TA-lib ones. These have 20 years of C-optimizations. I wasnt able to break the speed-records of TA-lib with Pure Polars, Numba etc. Meaning that I will check that documentation on TA-lib i wrote soon to make TA-lib 0.6.x more easily installable. 

I will stop fighting the GIL for now. It's feature day. I will test soon with 3.14t. 

[here](../examples/performance.txt) is the performance log for the indicators. It shows you exactly the performance of TA-lib's pure C against the Polars ones. Note that these tests are only done for 10000 records. I will do a second one to make sure that TA-lib holds up with a million records as well. 

But again: later.

Ultimately this will be rewritten to C++. For me, all of this, is also testing what works best and what are the DOs and DONts,

**Note:** When you run `./run-tests.sh` for performance tests and you see high values for marketprofile etc. `clear && ./run-tests.sh`. The numba extensions need to get compiled (cached). On a second run they will be cached and show you the `real values`.

Some "in-between" research, opted:

```sh
Actually, you’ve hit the nail on the head regarding the "Numba-Polars Bottleneck." When you use map_batches, 
you are trapped in a Double Serialization Tax:

- Polars to Python: Polars has to wrap the Rust-native memory into a Python Series object.
- Python to Numba: Numba has to inspect that Python object to find the underlying pointer to convert it to a numpy.ndarray.

Even with nogil=True, Numba only releases the GIL inside the compiled C-loop. The entry and exit points 
(where Series.to_numpy() happens) must hold the GIL because they are interacting with the Python C-API to 
resolve the memory address.

Can we bypass the GIL for serialization?

Technically, no, not while staying inside the standard map_batches(lambda s: ...) pattern. Python's memory 
management **is** the GIL.However, there is a "Pro" architectural way to solve this: 
The FFI (Foreign Function Interface) approach.

The Solution: Using numba.cfunc and Polars register_plugin

If you want to stop "re-entering" the GIL, you have to stop using Python as the middleman. Instead of passing 
data from Polars -> Python -> Numba, you can compile your Numba function into a standalone shared library 
that Polars calls directly via its Rust-based plugin system.
```

I will have a go on this. Seeing if the 'end-user`-complexity is not too much (can it be made 0-effort?). I want to remain Python-ness but operate at the C-level without that nasty GIL stuff.

## **Notice: Web-interface small issue**

No. The issue was the RSI indicator. Warmup was 3 * rsi_period. Made it * 15. Now all oke.

**Note:** RSI stabilization is subtle. Using `3 times period` for warmup is common but often results in floating-point drift. By utilizing a larger multiplier (e.g., `15 times`), these drifts are eliminated as the influence of the initial seed value diminishes toward zero, ensuring mathematical convergence across different data windows.

The performance impact of increasing the `period * 15` is minimal, microseconds.

**Note:** I tested using the HTTP-API. Throughput decreased from 340(avg) to 326 req/sec (avg).

**Note:** This is nitpicking. Rounded to two decimals there was no issue. It was an issue with the last 3 decimals. But for ML-setups these 3 decimals are definately relevant.

It looked like an interface issue but actually what happens, when you click "Update View", is that the `after_ms` and `until_ms` change, leading to different "data windows" and lengths. The seed value shifted, and when not enough buffer, that has impact, leading to convergence-issues. 

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

This is a second reason why your indicators should be optimal-and thus "future-ready".

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

