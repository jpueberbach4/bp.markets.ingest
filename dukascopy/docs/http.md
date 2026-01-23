# HTTP-Service (v0.6.6 and above)

This directory implements the HTTP-service feature for version 0.6.6.

## Functionalities:

- Expose CLI-like behavior over HTTP
- Support queries from Expert Advisors
- MT4 compatibility
- Health endpoint
- Basic HTML support for dashboards or minimal personalization
- Only listens on 127.0.0.1 (localhost)
- Configuration via central YAML config
- Binary Memory-mapped version

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

## Startup## Start/Stop/Status service

```sh
./service.sh start
./service.sh status
./service.sh stop
```

After starting service, open a browser and type ```http://localhost:8000/``` (change port if you change port in config.user.yaml).


## API Reference: OHLCV Endpoint, two main API versions (1.0 and 1.1)

The API uses a path-based Domain Specific Language (DSL) for primary filtering, followed by standard query parameters for pagination and cross-origin requests.

### Base URL
`http://localhost:8000/ohlcv/1.1/`

---

### Path Parameters (Positional DSL)

Timestamps are flexible and will be normalized to `YYYY-MM-DD HH:MM:SS`.

| Segment | Component | Description | Example |
| :--- | :--- | :--- | :--- |
| `select` | `{symbol},{tf}[{indicators}]` | **Required.** Asset symbol and timeframe (comma-separated). | `AAPL.US-USD,1h` |
| `after` | `{timestamp}` | Inclusive start time. Supports `.` or `-` and `,` or ` `. | `2025.11.22,13:59:59` or `1767992340000` (epoch_ms) |
| `until` | `{timestamp}` | Exclusive end time. Supports same flexible formatting. | `2025-12-22 13:59:59`  or `1767992340000` (epoch_ms) |
| `output` | `{format}` | Data format: `CSV`, `JSON`, or `JSONP`. | `JSONP` |
| `MT4` | *Optional* | Flag for MetaTrader 4 formatting (only valid with `output/CSV`). | `MT4` |

**Note**: Indicators need to be chained as following: [sma(9):macd(12,6,9):ema(200)] or, simplified, [sma_9:macd_12_6_9:ema_200]. Combinations of the two syntaxes are also possible but stick to one format. Chain as many if you like but take into account that the more indicator you add, the more performance you ask.

### Query Parameters

Used for windowing and wrapping responses.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `offset` | `integer` | `0` | Number of records to skip. |
| `limit` | `integer` | `100` | Maximum number of records to return. |
| `callback` | `string` | `__bp_callback` | **Use with JSONP.** Function name for the wrapper. |
| `subformat` | `integer` | `1..4` | **Use with JSON/JSONP.** Specifies the [response format](json.md). |
| `id` | `string` | `any string` | **Use with JSON/JSONP.** Assigns an id to the request which is returned in the output structure. |

---

### Normalization & Formats

#### Timestamp Normalization
The parser automatically cleans delimiters to ensure ISO-8601 compatibility:
* `2025.11.22,13:59:59` → `2025-11-22 13:59:59`
* `2025.11.22 13:59:59` → `2025-11-22 13:59:59`
* `1767992340000` (EPOCH_MS)

Internally timestamps are converted to EPOCH_MS. Milliseconds past since EPOCH.

#### JSONP Usage
When `output/JSONP` is specified, the response is wrapped in the function name provided by the `callback` query parameter.
* **Format:** `callback_name({...data...})`

---

### Example Requests

**Standard JSONP Request:**
```sh
GET /ohlcv/1.1/select/AAPL.US-USD%2C1h[ema_9:sma_10]/after/2025.11.22,00:00:00/until/ \ 
2025.12.22,04:00:00/output/JSONP?callback=my_handler&limit=5
```

**MT4 CSV Export:**
```sh
GET /ohlcv/1.1/select/EURUSD,1h[macd(12,6,9)]/after/2025.01.01+00:00:00/output/CSV/MT4
```

**Symbol list request:**
```sh
GET /ohlcv/1.1/list/indicators/output/JSON
```

**Indicator list request:**
```sh
GET /ohlcv/1.1/list/indicators/output/JSON
```

**Extensive example:**
```sh
GET http://localhost:8000/ohlcv/1.1/select/AAPL.US-USD,1h/ \
select/EUR-USD,1h:skiplast/after/2025.11.22,13:59:59/ \
until/2025-12-22+13:59:59/output/CSV
```

**Even more extensive example:**

```sh
GET http://localhost:8000/ohlcv/1.1/select/AAPL.US-USD,1h[sma_9:sma_20:ema_100:macd_12_6_9:bbands_12_2.0]/ \
after/1767992340000/output/JSON?subformat=3&executionmode=serial
```

**Serial execution mode:**

Serial execution mode passes the output of the first indicator into the second, the outputs of the first and second into the third, and so on. While not yet supported, this feature is coming soon. \
\
The goal is to enable ordered chaining of system indicators, where all preceding indicator outputs are fed into a custom indicator. This allows the custom indicator to operate on all generated columns efficiently and in a fully vectorized way, without leaving main memory or triggering recomputation. \
\
In effect, this provides pipelining within a single HTTP API request, with minimal additional effort. Virtual indicators will also be supported, allowing you to configure an indicator chain and assign it a virtual ID. That virtual ID is expanded and resolved at request time. \
\
Also, this prevents huge monolitic indicators. Something i am already battling with. Another added benefit is that you can better debug the individual components that provide the input for your very powerful custom indicator. Since the current "parallel" mode is just timesharing on the same CPU, there will be no expected performance degradation on using this mode. In fact, it may even be faster because of no more context switching, improving CPU cache utilization. \
\
The last indicator in the chain will be able to specify the final output columns. Aka it can drop intermediate columns not needed in the output.

Braindump-example virtual indicator config file:

```yaml
risk_on:
  indicators:
  - parallel: [ema(21), ema(55)]          # expliciet parallel groep
  - parallel: [rsi(14), stoch(14,3,3)]
  - supertrend(10,3)
  - my_risk_on_entry
  prune:
  - sma_21
  - sma_55
  - supertrend_10_3
```

Example call:

```sh
GET http://localhost:8000/ohlcv/1.1/select/AAPL.US-USD,1h[risk_on]/....
``` 


**Note:** Modifier `panama` is unsupported via the API.

**Note:** API is limited to a limit of 100.000 records. If you need more, use until/after and multiple requests.

**Note:** No rate-limits.

## Standard HTML support

Below the root of the endpoint you can servce your own HTML/JS/CSS documents. You should put these documents below the root configured in `config.user.yaml`. Default this location is `config/dukascopy/http-docs`.

For an example on how to use this API for chart generation, [see here](../config/dukascopy/http-docs/index.html).

There is also an `indicator.html` and a bit glitchy `replay.html` - both are demo-scripts.

## Output format

Various output formats are supported. Output-mode can be altered by using the `/output/{type}?subformat=[1..4]` construction.
CSV mode and JSON subformat 4 are "streaming modusses".

For more information on (currently supported) JSON formats, see [here](json.md).

**Note:** a self-describing high performance streaming binary format will soon be added too.

## Indicators

### Limitations and Future Evolution (v1.0 vs v1.1)

API Version 1.1 is now the only version. 1.0 has been stripped for maintainability.

### Custom indicators

Are supported. See [here](indicators.md) for more information.

### Indicator list

**RSI**

The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and magnitude of recent price changes to evaluate overbought or oversold conditions in an asset. It oscillates on a scale from 0 to 100, with readings typically above 70 indicating that a security is becoming overvalued (overbought) and readings below 30 suggesting it is undervalued (oversold). Traders use these levels to anticipate potential trend reversals or corrective pullbacks, often looking for "divergences" where the price and RSI move in opposite directions to confirm a weakening trend.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[rsi_14]/after/2026-01-01+00:00:00/output/JSON?order=desc
```

**SMA**

The Simple Moving Average (SMA) is a basic technical indicator that calculates the average price of an asset over a specific number of time periods by summing the closing prices and dividing by the count. It is primarily used to smooth out price volatility and identify the underlying trend direction by filtering out short-term market "noise." Because it relies equally on all data points within its window, it tends to lag behind current price action more than weighted or exponential averages.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[sma_20]/after/2026-01-01+00:00:00/output/JSON?order=desc
```

**EMA**

The Exponential Moving Average (EMA) is a type of moving average that places a greater weight and significance on the most recent data points, making it more responsive to new price information than a Simple Moving Average. It is widely used by traders to identify trend direction and potential reversal points by smoothing out price fluctuations while minimizing the "lag" associated with older data. Because the EMA reacts more quickly to price changes, it is often favored for identifying short-term momentum shifts and as a primary component in complex indicators like the MACD.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[ema_20]/after/2026-01-01+00:00:00/output/JSON?order=desc
```

**MACD**

The Moving Average Convergence Divergence (MACD) is a trend-following momentum indicator that calculates the difference between a 12-period and a 26-period Exponential Moving Average (EMA). It consists of a MACD line, a signal line (a 9-period EMA of the MACD line), and a histogram that visualizes the distance between the two. Traders look for crossovers between these lines and movements above or below the center zero line to identify shifts in trend direction and momentum.


```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[macd_12_26_9]/after/2026-01-01+00:00:00/output/JSON?order=desc
```

**Bollinger**

Bollinger Bands are a volatility-based technical indicator consisting of a middle Simple Moving Average (SMA) and two outer bands plotted at a standard deviation distance above and below it. The bands automatically expand during periods of high market volatility and contract during stable periods, providing a visual representation of price relative to historical norms. Traders typically use the indicator to identify overbought conditions when price touches the upper band or oversold conditions at the lower band, often anticipating a "mean reversion" back toward the middle average.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[bbands_14_2.0]/until/2026-01-01+00:00:00/output/JSON?order=desc
```

**ATR**

The Average True Range (ATR) is a volatility indicator that measures the market's "breathing room" by calculating the average range between price highs and lows over a set period, typically 14 days. Unlike momentum oscillators, it does not indicate price direction, but rather the degree of price movement or "noise" present in the market. Traders primarily use it to set dynamic stop-loss levels that expand during high volatility and tighten when the market is quiet to avoid being prematurely stopped out.

```sh
GET http://localhost:8000/ohlcv/1.1/select/BTC-USD,1d[atr_14]/output/JSON?order=desc
```

**STOCHASTIC**

The Stochastic Oscillator is a momentum indicator that measures the current closing price of an asset relative to its high-low range over a specific period, typically 14 days. It utilizes a scale from 0 to 100 to identify overbought conditions above 80 and oversold conditions below 20, signaling where price reversals may occur. By tracking the speed of price movement through its %K and %D lines, it helps traders anticipate trend changes before they appear in the actual price action.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[stochastic_14_3]/output/JSON?order=desc
```

**ADX**

The Average Directional Index (ADX) is a non-directional technical indicator used to quantify the strength of a price trend on a scale from 0 to 100. It typically identifies a strong trend when the value rises above 25 and a weak or ranging market when it falls below 20. While it measures trend intensity regardless of direction, it is often paired with Positive (+DI) and Negative (-DI) indicators to determine whether that trend is bullish or bearish.


```sh
GET http://localhost:8000/ohlcv/1.1/select/BTC-USD,1h[adx_14]:skiplast/output/JSON?order=desc
```

**VWAP**

The Volume-Weighted Average Price (VWAP) is a technical indicator that calculates the average price of an asset based on both its trading volume and price throughout a specific period. It serves as a benchmark for institutional traders to determine if they are buying or selling at a price better or worse than the market average, helping to minimize market impact. Unlike a simple moving average, VWAP is usually "anchored" to a specific start time, such as the market open, and provides a true reflection of price levels where the most significant trading activity occurred.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[vwap]/after/2026.01.01,00:00:00/output/JSON?order=desc
```

**Parabolic SAR**

The Parabolic SAR (Stop and Reverse) is a trend-following indicator used to identify potential market reversals and determine optimal exit points. It appears as a series of dots placed above or below price bars, where a position below the price suggests a bullish trend and a position above indicates a bearish trend. The indicator is unique for its "acceleration factor," which causes the dots to move closer to the price as a trend strengthens, automatically tightening trailing stop-losses to lock in profits.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[psar(0.01,0.1)]/output/JSON?order=desc&limit=1-0
```

**Keltner Channels**

Keltner Channels are a volatility-based envelope indicator consisting of a central exponential moving average and two bands derived from the Average True Range (ATR). Unlike Bollinger Bands, which use standard deviation, Keltner Channels provide a smoother boundary that is less sensitive to extreme price outliers, making them highly effective for identifying trend breakouts. Traders typically look for price staying above the upper band to confirm strong bullish momentum or using the bands as dynamic support and resistance levels.

```sh
GET http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[keltner(20,2.5)]/output/JSON?order=desc
```

For a complete index of all available indicators, call:

```sh
GET http://localhost:8000/ohlcv/1.1/list/indicators/output/JSON
```

Or see the indicator selection dropdown in `http://localhost:8000/index.html`. You can export indicator output to CSV from this URL as well.

### Performance Characteristics (typical laptop environment)

Performance price only: 8-10 ms for 1000 records, 1m EUR-USD.
Performance price+indicators: +/- 15 ms for 1000 record (1 indicator), 1m EUR-USD.

**Note:** Endpoint has been hammered with 100.000 heavy query requests overnight. 0 failures. Very stable.

**Theoretical performance thread-optimized version**

| Metric | Single-threaded | 16-Core Optimized | Factor | Kubernetes |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (QPS)** | 22 (1m data) | 300–350 | **15x** | Virtually unlimited |
| **Concurrent users** | 5 | 50–80 | **10–16x** | Virtually unlimited |
| **Response time (p95)** | 46ms | 15–20ms | **2–3x faster** | Same base stats |
| **Memory usage** | 50–100MB | 800MB–1.5GB | 8–15x | 1024MB per pod |

If you need a thread optimized version, optionally NUMA-aware, you can contact me at jtrader25@gmail.com.
