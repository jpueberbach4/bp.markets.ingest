# Replay

## Introduction

The replay subsystem provides a deterministic, time-ordered market data stream that can be replayed, inspected, and transformed exactly as if it were live. Its primary purpose is to enable reproducible analysis, plugin experimentation, and time-travel debugging across mixed timeframes and multiple assets.

At a high level, the replay pipeline consists of two stages:

1. Dataset construction – generating a single, ascending, mixed-timeframe candle stream.

2. Replay – emitting candles in correct chronological order, aligned to their effective close times, and streaming them through an arbitrary analysis chain.

## Mixed-Timeframe CSV Generation

The build-(csv|parquet).sh script produces a unified CSV/Parquet containing candles from multiple assets and timeframes (e.g. 1m, 5m, 15m, 1h). All candles are sorted in ascending time order, forming the canonical input for replay.

Example:

```sh
build-csv.sh \
  --select EUR-USD/1m,5m,15m \
  --select GBP-USD/1m,5m,15m,1h \
  --output replay.csv
```

This CSV becomes the single source of truth for downstream replay and analysis.

## Deterministic Replay Engine

The replay.sh script reads the mixed-timeframe CSV and emits candles as a continuous stream in correct chronological order. Each candle is aligned to its right boundary (close time):

- A 15-minute candle starting at 13:00:00 is emitted at 13:14:59
- A 1-minute candle starting at 13:00:00 is emitted at 13:00:59

This alignment guarantees that higher-timeframe candles appear after all constituent lower-timeframe candles, exactly as they would in a live environment.

Example:

```sh
replay.sh --input replay.csv | analyse.sh
```

Internally, replay leverages in-memory DuckDB to efficiently merge, sort, and stream data while maintaining strict temporal correctness.

## Streaming, Chaining, and Plugins

Replay output is designed to behave like a live feed. Candles flow continuously and can be piped through any number of processing stages using standard UNIX composition.

All components are fully chainable:

```sh
replay.sh --speed 10 \
  --input replay.csv \
  --mix-with calendar-events.csv \
  --mix-with FOMC-5-minutes-before.csv | \
  tee raw.txt | \
  indicator.sh | \
  tee indicator.txt | \
  analyse.sh | \
  tee analyse.txt | \
  imagine.sh > output.txt
```

Plugins operate by appending new columns to the incoming stream (e.g. indicators, events, derived signals). Because the stream is append-only and strictly ordered, correctness is easy to validate.

For example, indicator output can be live-tailed during replay:

```sh
tail --follow indicator.txt
```

This makes it trivial to confirm that indicators are computed incrementally and aligned correctly in time.

## Design Philosophy

The replay system is intentionally minimal and UNIX-native. Rather than embedding logic in a monolithic framework, it provides:

- Full control over the analysis stack
- Language-agnostic tooling (shell, Python, C++, awk, Rust, etc.)
- Arbitrary chaining of components
- Reproducible experiments
- Time-travel debugging by replaying the exact same stream

This approach leverages over 50 years of proven UNIX tooling while remaining flexible enough to support complex, event-driven market analysis. Injecting new data sources or transformations is simply a matter of implementing the agreed streaming interface.

etc...

There is more. Ie stop, pause, resume a stream by it's id. Alter the speed during runtime. Logging to default files which then can be visualized through the HTTP API and dashboards. And so on. This is a preliminary document.