# HTTP-Service (v0.6) - BETA

This directory implements the HTTP-service feature for version 0.6.

## Functionalities:

- Expose CLI-like behavior over HTTP
- Support queries from Expert Advisors
- MT4/MT5 compatibility
- Additional features to be added iteratively for seamless integration
- Metrics endpoint running in a separate thread
- Health endpoint running in a separate thread
- Basic HTML support for dashboards or minimal personalization
- Only listens on 127.0.0.1 (localhost)
- Configuration via central YAML config
- Design and API specification will be published

## Prerequisites

```sh
pip install requirements.txt
```

## Configuration

A block in the ```config.user.yaml``` needs to get added

```yaml
## Below you will find the configuration for the http service script.
http:
  docs: config/dukascopy/http-docs    # Directory where HTML docs will live
  listen: ":8000"                     # Listen to this port
  limits:
    max_page: 1000                    # Maximum number of pages to support
    max_per_page: 1000                # Maximum number of rows per page
```

Or, if using default configuration, ```./setup-dukascopy.sh```.

## Start/Stop/Status service

```sh
./service.sh start
./service.sh status
./service.sh stop
```

## URI definition

While not necessarily optimal, this approach provides full compatibility with the builder’s select options. By mirroring the builder syntax exactly, the API remains intuitive and easy to learn: if you know the builder syntax, you already know the URI syntax, and vice versa.

```sh
http://localhost:8000/ohlcv/1.0/select/AUD-USD:test,1h,4h/after/2025-01-01+00:00:00 \
output/JSON?order=asc&limit=3
```

Outputs can be:

- JSON \
  Simple JSON records
- JSONP \
  Simple JSON records wrapped with a callback method
- CSV \
  Pure CSV text

If you want JSONP with a callback, example:

```sh
http://localhost:8000/ohlcv/1.0/select/AUD-USD,1h,4h/select/EUR-USD,1h/after/2025-01-01+00:00:00 \
/output/JSONP?order=asc&limit=3&callback=__my_callback
```

Another example

```sh
http://localhost:8000/ohlcv/1.0/select/AUD-USD,1h/select/EUR-USD,1h/after/2025-12-01+00:00:00 \
/output/JSON?order=desc&limit=50&offset=0
```

## Output formats 

Example output for above example URL

```json
{
  "status": "ok",
  "result": [
    {
      "symbol": "AUD-USD",
      "timeframe": "4h",
      "year": "2025",
      "time": "2025-01-02 00:00:00",
      "open": 0.61804,
      "high": 0.62149,
      "low": 0.61796,
      "close": 0.6211,
      "volume": 15103.04
    },
    {
      "symbol": "AUD-USD",
      "timeframe": "1h",
      "year": "2025",
      "time": "2025-01-02 01:00:00",
      "open": 0.61856,
      "high": 0.61939,
      "low": 0.61821,
      "close": 0.6193,
      "volume": 3189.15
    },
    {
      "symbol": "AUD-USD",
      "timeframe": "1h",
      "year": "2025",
      "time": "2025-01-02 02:00:00",
      "open": 0.6193,
      "high": 0.62026,
      "low": 0.61878,
      "close": 0.62,
      "volume": 3675.22
    }
  ]
}
```

More information will be added soon
