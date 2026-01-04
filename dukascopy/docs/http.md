# HTTP-Service (v0.6)

This directory implements the HTTP-service feature for version 0.6.

## Functionalities:

- Expose CLI-like behavior over HTTP
- Support queries from Expert Advisors
- MT4 compatibility
- Health endpoint
- Basic HTML support for dashboards or minimal personalization
- Only listens on 127.0.0.1 (localhost)
- Configuration via central YAML config

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
```

Or, if using default configuration, ```./setup-dukascopy.sh```.

## Start/Stop/Status service

```sh
./service.sh start
./service.sh status
./service.sh stop
```

After starting service, open a browser and type ```http://localhost:8000/``` (change port if you change port in config.user.yaml).

## API Reference: OHLCV Endpoint

The API uses a path-based Domain Specific Language (DSL) for primary filtering, followed by standard query parameters for pagination and cross-origin requests.

### Base URL
`http://localhost:8000/ohlcv/1.0/`

---

### Path Parameters (Positional DSL)

Timestamps are flexible and will be normalized to `YYYY-MM-DD HH:MM:SS`.

| Segment | Component | Description | Example |
| :--- | :--- | :--- | :--- |
| `select` | `{symbol},{tf}` | **Required.** Asset symbol and timeframe (comma-separated). | `AAPL.US-USD,1h` |
| `after` | `{timestamp}` | Inclusive start time. Supports `.` or `-` and `,` or ` `. | `2025.11.22,13:59:59` |
| `until` | `{timestamp}` | Exclusive end time. Supports same flexible formatting. | `2025-12-22 13:59:59` |
| `output` | `{format}` | Data format: `CSV`, `JSON`, or `JSONP`. | `JSONP` |
| `MT4` | *Optional* | Flag for MetaTrader 4 formatting (only valid with `output/CSV`). | `MT4` |

### Query Parameters

Used for windowing and wrapping responses.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `offset` | `integer` | `0` | Number of records to skip. |
| `limit` | `integer` | `100` | Maximum number of records to return. |
| `callback` | `string` | `__bp_callback` | **Use with JSONP.** Function name for the wrapper. |

---

### Normalization & Formats

#### Timestamp Normalization
The parser automatically cleans delimiters to ensure ISO-8601 compatibility:
* `2025.11.22,13:59:59` → `2025-11-22 13:59:59`
* `2025.11.22 13:59:59` → `2025-11-22 13:59:59`

#### JSONP Usage
When `output/JSONP` is specified, the response is wrapped in the function name provided by the `callback` query parameter.
* **Format:** `callback_name({...data...})`

---

### Example Requests

**Standard JSONP Request:**
```sh
GET /ohlcv/1.0/select/AAPL.US-USD%2C1h/after/2025.11.22/until/2025.12.22/output/JSONP? \
callback=my_handler&limit=5
```

**MT4 CSV Export:**
```sh
GET /ohlcv/1.0/select/EURUSD,1h/after/2025.01.01/output/CSV/MT4
```

**List request:**
```sh
GET /ohlcv/1.0/list/output/JSON
```

**Extensive example:**
```sh
GET http://localhost:8000/ohlcv/1.0/select/AAPL.US-USD,1h/ \
select/EUR-USD,1h/after/2025.11.22,13:59:59/ \
until/2025-12-22+13:59:59/output/CSV
```

For an example on how to use this API for chart generation, [see here](../config/dukascopy/http-docs/index.html).

## Output format

Example output for JSON URL

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

## Example Error output - Always JSON, statuscode 400

```json
{
  "status": "failure",
  "exception": "MT4 flag requires output/CSV",
  "options": {
    "select_data": [
      [
        "AAPL.US-USD",
        "1h",
        "/home/jpueberb/repos2/bp.markets.ingest/dukascopy/data/resample/1h/AAPL.US-USD.csv",
        []
      ]
    ],
    "after": "2025-11-22 13:59:59",
    "until": "2025-12-22 13:59:59",
    "output_type": "JSON",
    "mt4": true,
    "limit": 1440,
    "offset": 0,
    "order": "asc",
    "callback": "__bp_callback"
  }
}
```

