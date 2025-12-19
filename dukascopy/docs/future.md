## Notes and Future Work

>HTTP API for OHLC retrieval (0.6)
```sh
scratchpad:
# Mapping CLI-alike behavior to HTTP. We will only support 127.0.0.1 (legal-boundary). No CORS *. It's for EA purposes.
http://localhost:port/api/v1/ohlc/select/SYMBOL,TF1,TF2:skiplast/select/SYMBOL,TF1/after/2025-01-01+00:00:00/output/CSV/MT4
# will be better than this. 

# Health endpoint
http://localhost:port/healtz
# Metrics endpoint (performance, total bytes, number of requests, response times etc)
http://localhost:port/metrics

Or something similar. Need to check industry standards (best UX/elegancy).
```

>Replay functionality (0.7)

```sh
scratchpad:
# Generates a time-ordered (ascending) CSV containing mixed 1m/5m/15m candles 
# across multiple assets.
build-csv.sh --select EUR-USD/1m,5m,15m --select GBP-USD/1m,5m,15m,1h --select ... --output replay.csv 

# Replays the mixed-timeframe candle stream. 
# replay.sh aligns candles to their right boundary (e.g., 15m candle at 13:00:00 
# becomes 13:14:59, 1m candle 13:00:00 → 13:00:59) and emits them in correct 
# chronological order. The output can be piped directly into the next analysis stage.
replay.sh --input replay.csv | analyse.sh 

# Candles flow in continuously and in correct order.
# This is an experiment leveraging in-memory DuckDB.

# Plugins will be fully chainable:
replay.sh --speed 10 --input replay.csv | --mix-with calendar-events.csv \
--mix-with FOMC-5-minutes-before.csv | tee raw.txt | indicator.sh | tee indicator.txt | \
analyse.sh | tee analyse.txt | ... | imagine.sh > output.txt

# Live tailing of indicator.txt to confirm that indicator scripts are correctly appending new columns 
# to the incoming stream with the correct values.
tail --follow indicator.txt

# Results so far are very promising.

# Why this approach?
# It gives complete control over the analysis stack, powered by 50+ years of 
# UNIX tooling. Use any programming language, chain any number of components, 
# perform time-travel debugging—limitless flexibility.

# For me, this is a dream, if this is done. There is a need for smart interface design 
# here so injecting something in new in the stream is just a matter of implementing 
# that interface. Will be fine.

```

~~**Goal:** Wrap up the above two functionalities into an MVP before Christmas, so I can resume C++ work at the start of next year. Current codebase is under 1,500 lines of actual LOC; target is to stay below 3,000.~~

**Goal:** Before end of year finishing up the data (100 percent correctness against MT4 is the target, currently ~95 percent). First two weeks of next year round up above two features with a basic set of plugins (SMA, EMA, MACD, RSI, Bollinger, perhaps others). Happy holidays :)

>Idea (unexplored): ~~If feasible and data access allows, get approval to replay financial calendar events through replay.sh as "control structures". This is something I’ll likely need as well, but it hasn’t been explored yet (0.8 feature?)~~. I will provide for the option of multiple --mix-with flag. If you have a CSV with ```timestamp,customdata1,customdata2,...``` it will push the customdata1,customdata2 in the outgoing eventstream exactly on that timestamp. This way you can mix anything into it. Including calendar events. This is for the first version. Later i will have a look if we can obtain that calendar data without breaking any TOS. 

>Cascaded indicator engine (1.0) (if still needed after replay.sh + plugins)

>MSSIB Extension for DuckDB

>C++ advanced concepts for trading (study)