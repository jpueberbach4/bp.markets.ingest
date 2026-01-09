## Limitations

At present, the tool has no known limitations relative to the MT4 platform. I’ve conducted a pretty thorough review, but it’s possible some issues were missed. If you notice anything that should be fixed, please report it via the repository’s Discussions.

Generally speaking, this platform emulates MT4 alignment pretty excellent. In binary mode this pipeline is really fast.

See [Tests](tests.md)

## Open issues / To do list

**P1 (Critical):**
- Replay/Market simulation via "event streaming" \
  This has top-priority. Building an event-stream that handles the anomalous candles and is fully \
  deterministic by design. Pipe-able through default UNIX pipes. This is why this project exists. \
  Building my own, high-performance, backtester that is not a monolith.
- Custom shifting for ASX 2020 anomaly \
  Planned end of this month
- Custom shifting for one-week-leap-year DST lag (affects Nov 2020,2024,2028,etc) \
  Planned end of this month

**P2 (Important):**
- HTTP API for version 1.1 with single-stream indicator support \
  API 1.0 currently has seperate indicator support. We would like to have indicators integrated into the price stream. \
  **Note:** Best to do this in the builder component and import that to HTTP-API. Benefit is that a user can also use the \
  builder to generate "indicator-enriched" CSV/Parquet files. Risk: 1.0 API will also support the new select syntax because \
  it also inherits from builder. Make sure backward compat remains. Optional extra DSL-based [..] is not an issue. \
  Means that API 1.0 will automatically transition too. The extra thing the 1.0 API will have is the current indicator support.
- Profile/Optimize startup time of resample \
  Resample is incredibly fast but in incremental mode it seems to have a startup lag. Profile it. \
  Likely `resample_get_symbol_config` is the issue. One more optimization pass needed here.
- MIN-MAX date-range API \
  Currently the 1.0 API has "history searching" because it doesnt know the first timestamp of the first available data. \
  A range API call will eliminate it.
- Stock split support \
  This was an external request. Provide configuration support to "level-out" stock splits.

**P3 (Nice-to-have):**
- Further performance improvements (eg. partitioning of data) \
  This is mainly to increase performance of the web-service by a huge factor. It's already blazing but i am still not \
  100 percent satisfied with it.
- Track a live-backadjusted 1m base-including resampling- in a seperate directory (configurable) \
  This is a personal "must-have". Currently i build the backadjusted data via a cronjob and its CSV \
  I need a backadjusted BINARY version. It's a format mismatch for my "other code". \
  Backadjusted base gets automatically rebuild once a month (on rollover)

**P4 (Architectural):**
- Add some LRU caches here and there for processes that are continuously running \
  In order to make it "live-ready" LRU caching needs to be implemented here and there. \
  There are a few expensive (mostly config related) routines that will massively benefit from LRU \
  Do not change the current code. Just write a decorator if default LRU just cannot cut it.
- General QA improvements \
  Builder component is currently the worst component. Needs a refactor to OOP.
- Librarization \
  Bit by bit things get ready for a library.

This is still in an MVP state. Although working very well. It's an MVP.


