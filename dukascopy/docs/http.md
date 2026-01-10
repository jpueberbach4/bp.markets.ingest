# HTTP-Service (v0.6.5 and above)

This directory implements the HTTP-service feature for version 0.6.5.

## Functionalities:

- Expose CLI-like behavior over HTTP
- Support queries from Expert Advisors
- MT4 compatibility
- Health endpoint
- Basic HTML support for dashboards or minimal personalization
- Only listens on 127.0.0.1 (localhost)
- Configuration via central YAML config
- Text / Binary Memory-mapped version

## Breaking change when switching to 0.6.5

This version is a breaking change version for the API. `http-service` directory name was not a very friendly python name. There were issues with including files that had to be resolved-in order to prepare for the v1.1 API release. After updating, perform:

```sh
killall python3
./service.sh start
```

Brute force is fine. It can handle it.

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
GET /ohlcv/1.0/select/AAPL.US-USD%2C1h/after/2025.11.22,00:00:00/until/ \ 
2025.12.22,04:00:00/output/JSONP?callback=my_handler&limit=5
```

**MT4 CSV Export:**
```sh
GET /ohlcv/1.0/select/EURUSD,1h/after/2025.01.01+00:00:00/output/CSV/MT4
```

**List request:**
```sh
GET /ohlcv/1.0/list/output/JSON
```

**Extensive example:**
```sh
GET http://localhost:8000/ohlcv/1.0/select/AAPL.US-USD,1h/ \
select/EUR-USD,1h:skiplast/after/2025.11.22,13:59:59/ \
until/2025-12-22+13:59:59/output/CSV
```

**Note:** Modifier `panama` is unsupported via the API.

**Note:** API is limited to a limit of 1440 records. Perform multiple calls for bigger sets, use after/until.

**Note:** No rate-limits on this one ;)

## Standard HTML support

Below the root of the endpoint you can servce your own HTML/JS/CSS documents. You should put these documents below the root configured in `config.user.yaml`. Default this location is `config/dukascopy/http-docs`.

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


## Indicators

**Limitations and Future Evolution (v1.0 vs v1.1)**

While the current v1.0 indicator implementation is functional, it is not yet optimal for professional-grade technical analysis. Because the current engine heavily re-uses the "regular select" logic, the API treats indicators as secondary filters rather than integrated data streams. 

This leads to a warmup period discrepancy: the engine currently drops the first N-rows starting from your after date to accommodate calculations, meaning the response may lack data for the specific start time you requested. To resolve these synchronization issues, we are transitioning to a more robust architecture:

- Version 1.0 (Legacy Support): This version will remain available for existing integrations and simple queries. It is reliable for basic data fetches but requires manual handling of lookback periods and limits.

- Version 1.1 (Next Gen): The upcoming 1.1 API will introduce an integrated selection logic where warmup periods are handled internally. It will automatically fetch the necessary historical data to ensure your requested after date contains a stable, accurate indicator value from the very first row of the response.

**RSI**

The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and magnitude of recent price changes to evaluate overbought or oversold conditions in an asset. It oscillates on a scale from 0 to 100, with readings typically above 70 indicating that a security is becoming overvalued (overbought) and readings below 30 suggesting it is undervalued (oversold). Traders use these levels to anticipate potential trend reversals or corrective pullbacks, often looking for "divergences" where the price and RSI move in opposite directions to confirm a weakening trend.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/rsi/period/14/select/EUR-USD,1h/after/2025-12-01+00:00:00/output/JSON?order=desc
```

**SMA**

The Simple Moving Average (SMA) is a basic technical indicator that calculates the average price of an asset over a specific number of time periods by summing the closing prices and dividing by the count. It is primarily used to smooth out price volatility and identify the underlying trend direction by filtering out short-term market "noise." Because it relies equally on all data points within its window, it tends to lag behind current price action more than weighted or exponential averages.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/sma/period/20/select/EUR-USD,1h/after/2025-12-01+00:00:00/output/JSON?order=desc
```

**EMA**

The Exponential Moving Average (EMA) is a type of moving average that places a greater weight and significance on the most recent data points, making it more responsive to new price information than a Simple Moving Average. It is widely used by traders to identify trend direction and potential reversal points by smoothing out price fluctuations while minimizing the "lag" associated with older data. Because the EMA reacts more quickly to price changes, it is often favored for identifying short-term momentum shifts and as a primary component in complex indicators like the MACD.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/ema/period/50/select/EUR-USD,1h/after/2025-12-01+00:00:00/output/JSON?order=desc
```

**MACD**

The Moving Average Convergence Divergence (MACD) is a trend-following momentum indicator that calculates the difference between a 12-period and a 26-period Exponential Moving Average (EMA). It consists of a MACD line, a signal line (a 9-period EMA of the MACD line), and a histogram that visualizes the distance between the two. Traders look for crossovers between these lines and movements above or below the center zero line to identify shifts in trend direction and momentum.


```sh
GET http://localhost:8000/ohlcv/1.0/indicator/macd/fast/12/slow/26/signal/9/select/EUR-USD,1h/after/2025-12-01+00:00:00/output/JSON?order=desc
```

**Bollinger**

Bollinger Bands are a volatility-based technical indicator consisting of a middle Simple Moving Average (SMA) and two outer bands plotted at a standard deviation distance above and below it. The bands automatically expand during periods of high market volatility and contract during stable periods, providing a visual representation of price relative to historical norms. Traders typically use the indicator to identify overbought conditions when price touches the upper band or oversold conditions at the lower band, often anticipating a "mean reversion" back toward the middle average.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/bbands/period/14/std/2.0/select/EUR-USD,1h/until/2025-12-31+00:00:00/output/JSON?order=desc
```

**ATR**

The Average True Range (ATR) is a volatility indicator that measures the market's "breathing room" by calculating the average range between price highs and lows over a set period, typically 14 days. Unlike momentum oscillators, it does not indicate price direction, but rather the degree of price movement or "noise" present in the market. Traders primarily use it to set dynamic stop-loss levels that expand during high volatility and tighten when the market is quiet to avoid being prematurely stopped out.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/atr/select/BTC-USD,1d/period/14/output/JSON?order=desc
```

**STOCHASTIC**

The Stochastic Oscillator is a momentum indicator that measures the current closing price of an asset relative to its high-low range over a specific period, typically 14 days. It utilizes a scale from 0 to 100 to identify overbought conditions above 80 and oversold conditions below 20, signaling where price reversals may occur. By tracking the speed of price movement through its %K and %D lines, it helps traders anticipate trend changes before they appear in the actual price action.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/stochastic/select/EUR-USD,1h/k_period/14/d_period/3/output/JSON?order=desc
```

**ADX**

The Average Directional Index (ADX) is a non-directional technical indicator used to quantify the strength of a price trend on a scale from 0 to 100. It typically identifies a strong trend when the value rises above 25 and a weak or ranging market when it falls below 20. While it measures trend intensity regardless of direction, it is often paired with Positive (+DI) and Negative (-DI) indicators to determine whether that trend is bullish or bearish.


```sh
GET http://localhost:8000/ohlcv/1.0/indicator/adx/select/BTC-USD,1h:skiplast/period/14/output/JSON?order=desc
```

Above will remain in the 1.0 API. You can use it safely, although its not optimal atm.

**Sorting DESCENDING is currently a good practice**

## Version 1.1

```sh
GET http://localhost:8000/ohlcv/1.1/select/AAPL.US-USD,1h[sma(20,50),ema(50),macd(12,26,9)]:skiplast/ \
select/EUR-USD,1h:skiplast/after/2025.11.22,13:59:59/until/2025-12-22+13:59:59/output/JSON

```

The Version 1.1 API introduces a unified selection logic that shifts from sequential processing to a single-stream data architecture. By embedding indicator definitions directly within the selection brackets [...], the engine can perform all mathematical calculations in one pass. 

This version extends the default OHLCV response by injecting a dedicated indicators subsection into every price unit, ensuring that indicators are perfectly time-aligned with their corresponding candles.

Example:

```json
{
  "symbol": "AAPL.US-USD",
  "timeframe": "1h",
  "data": [
    {
      "time": "2025-11-22 14:00:00",
      "open": 150.00,
      "high": 155.00,
      "low": 149.00,
      "close": 152.00,
      "volume": 1200,
      "indicators": {
        "sma_20": 151.20,
        "sma_50": 148.50,
        "ema_50": 149.10,
        "macd_12_26_9": {
          "line": 1.2,
          "signal": 0.8,
          "hist": 0.4
        }
      }
    }
  ]
}
```

**Note:** If you need to identify your JSON request with an id, you can use `?callback=id` for that. It will return the callback value in the options.

## Thread safety

Currently, we are running the API requests in a single-threaded event-loop. This is sufficient for most use-cases. We have not programmed for a high-concurrency, ludacrous, online enterprise environment. If you want the API to handle such environments. You can contact me on the e-mail adres shown in the commit messages. Note that i will not support "distributive" environments, paid or unpaid. High performance research environments requiring an HTTP API that scales ONLY.