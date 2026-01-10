# Replay

## Introduction

The replay subsystem provides a deterministic, time-ordered market data stream that can be replayed, inspected, and transformed exactly as if it were live. Its primary purpose is to enable reproducible analysis, plugin experimentation, and time-travel debugging across mixed timeframes and multiple assets.

At a high level, the replay pipeline consists of two stages:

1. Dataset construction – generating a single, ascending, mixed-timeframe candle stream.

2. Replay – emitting candles in correct chronological order, aligned to their effective close times, and streaming them through an arbitrary analysis chain.

## Revised Vision

The introduction of the new binary format has prompted a shift in our vision. Previously, the plan was to first build a dataset and then use that dataset for replay. This approach is changing.

Instead, replay will use the same select syntax as the builder and the HTTP component.

As we are extending the selection syntax to include indicator generation—for example:

```sh
--select EUR-USD,1h[ema(20),ema(50),ema(200),macd(12,26,9)]:skiplast --select ...
```
—we have decided to support this exact syntax for replay as well. Replay will therefore operate directly on these select statements.

This approach provides several benefits:

- High-speed binary formats can be used directly as input

- Internal indicator engines can use the high-speed format

- A consistent and familiar command syntax across the entire platform

As a result, we also avoid chaining default-supported indicator scripts through UNIX pipes. This significantly shortens analysis pipelines and allows analysis scripts to be chained together more directly and efficiently.

The engine does not lose its deterministic input behavior since the binary input files are immutable, except for the last record, which can be excluded by using `:skiplast` or `--until`.

## Deterministic Replay Engine

The replay.sh script selects mixed-timeframes and mixed-symbols and emits candles as a continuous stream in correct chronological order. Each candle is aligned to its right boundary (close time):

- A 15-minute candle starting at 13:00:00 is emitted at 13:14:59
- A 1-minute candle starting at 13:00:00 is emitted at 13:00:59

This alignment guarantees that higher-timeframe candles appear after all constituent lower-timeframe candles, exactly as they would in a live environment.

Example:

```sh
replay.sh --select EUR-USD,1h[ema(20),ema(50),ema(200),macd(12,26,9)]:skiplast | analyse.sh
```

Internally, replay leverages zero-copy views and in-memory DuckDB to efficiently merge, sort, and stream data while maintaining strict temporal correctness.

One of the main goals, as always, is to achieve extreme performance. I am a performance enthusiast. I don't want to wait long for a historical analysis result. It should be near-instantaneous.

## Streaming, Chaining, and Plugins

Replay output is designed to behave like a live feed. Candles flow continuously and can be piped through any number of processing stages using standard UNIX composition.

All components are fully chainable:

```sh
replay.sh --speed 10 \
  ---select EUR-USD,1h[ema(20),ema(50),ema(200),macd(12,26,9)]:skiplast \
  --mix-with calendar-events.csv \
  --mix-with FOMC-5-minutes-before.csv | \
  tee raw.txt | \
  analyse.sh | \
  tee analyse.txt | \
  imagine.sh > output.txt
```

Plugins operate by appending new columns to the incoming stream (e.g. indicators, events, derived signals). Because the stream is append-only and strictly ordered, correctness is easy to validate.

For example, intermediate output can be live-tailed during replay:

```sh
tail --follow analyse.txt
```

This makes it trivial to confirm that intermediate data is computed incrementally and aligned correctly in time.

## Design Philosophy

The replay system is intentionally minimal and UNIX-native. Rather than embedding logic in a monolithic framework, it provides:

- Full control over the analysis stack
- Language-agnostic tooling (shell, Python, C++, awk, Rust, etc.)
- Arbitrary chaining of components
- Reproducible experiments
- Time-travel debugging by replaying the exact same stream

This approach leverages over 50 years of proven UNIX tooling while remaining flexible enough to support complex, event-driven market analysis. Injecting new data sources or transformations is simply a matter of implementing the agreed streaming interface.

## Eliminating Lookahead Bias by Design

In most backtesting frameworks, lookahead bias is a constant risk—it’s far too easy for an algorithm to accidentally "peek" at the Close price of a 1-hour candle while it is technically only halfway through that hour.

The Replay Subsystem eliminates this risk by moving away from "vectorized" backtesting and instead using a strictly chronological, boundary-aligned emission model.

## What makes this replay different from others

| Feature | Standard Replay | "This" Replay |
| :--- | :--- | :--- |
| **Emission Time** | Fixed (Start + Duration) | **Dynamic (Based on Session/Merge Logic)** |
| **Lookahead Bias** | High Risk (Vectorized) | **Eliminated (Boundary-Aligned)** |
| **Alignment** | Round numbers (1H, 4H) | **Anomalous (6h10m, HH:51, HH:10)** |
| **State** | Stateless | **Context-Aware (Date/Weekday specific)** |

The complexity lies in the fact that we aren't just replaying time; we are replaying state transitions.

There are multiple approaches to this problem. We can extend ETL to keep a record of "state" or we try to rebuild the state from the candles themselves using the configuration. We will first have a go at the second option. Will be "interesting".

State is a function of (timestamp, symbol, timeframe, config). If we can make that function deterministic and efficient, we'll have a truly unique and powerful replay system.

## Ideas

- Exposing statistics and logging through HTTP API
- STDERR to indicate progress, STDOUT for main pipeline streaming
- Support --pause, --resume, --restart, --stop, --speed with id to alter runtime state
- "Job"-files
- Concrete examples eg using AWK for analysis
- Code examples
- Extensive basic set of plugins

## Live

The first version will have semi-live support if you dont specify `--until`. When replay reaches a final higher-tf candle, it waits until it is completed, then emits it. So it will be able to replay history and automatically enter a `live-modus`. The switch to this modus will be announced to downstream scripts by publishing an identifiable event.

In short: reaches "now" → automatically switches to live-watch behavior

>In live-watch mode, the current developing candle(s) are emitted on every incoming lower-timeframe update in case a certain commandline-flag is set, eg `--emit-open-candle-updates`.

I will, eventually, reach out to the dataprovider in order to see if we can get a reliable lower-granularity live feed-paid or unpaid-to further streamline the integration with the dataprovider. Aka making it ready for the `second-level` market while being able to use the same chaining methodology.

If we are going to support second-level updates will be decided after these talks. The engines are capable.