# bp.markets.ingest

This repository implements the ingestion pipeline for marketdata

## Dukascopy

Dukascopy provides, free-of-charge, 1 minute OHLC candles for various instruments. Forex, Indices and stocks. We have written 3 components that load, transforms and inserts the data to 1m aggregated symbol files on which cascaded resampling happens in order to construct the various other timeframes.

See Dukascopy readme for additional details.