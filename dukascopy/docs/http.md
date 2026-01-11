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

**VWAP**

The Volume-Weighted Average Price (VWAP) is a technical indicator that calculates the average price of an asset based on both its trading volume and price throughout a specific period. It serves as a benchmark for institutional traders to determine if they are buying or selling at a price better or worse than the market average, helping to minimize market impact. Unlike a simple moving average, VWAP is usually "anchored" to a specific start time, such as the market open, and provides a true reflection of price levels where the most significant trading activity occurred.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/vwap/select/EUR-USD,1h/after/2025.01.01,00:00:00/output/JSON?order=desc
```

**Parabolic SAR**

The Parabolic SAR (Stop and Reverse) is a trend-following indicator used to identify potential market reversals and determine optimal exit points. It appears as a series of dots placed above or below price bars, where a position below the price suggests a bullish trend and a position above indicates a bearish trend. The indicator is unique for its "acceleration factor," which causes the dots to move closer to the price as a trend strengthens, automatically tightening trailing stop-losses to lock in profits.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/psar/step/0.01/max_step/0.1/select/EUR-USD,1h/after/2025.01.01/output/JSON
```

**Keltner Channels**

Keltner Channels are a volatility-based envelope indicator consisting of a central exponential moving average and two bands derived from the Average True Range (ATR). Unlike Bollinger Bands, which use standard deviation, Keltner Channels provide a smoother boundary that is less sensitive to extreme price outliers, making them highly effective for identifying trend breakouts. Traders typically look for price staying above the upper band to confirm strong bullish momentum or using the bands as dynamic support and resistance levels.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/keltner/period/20/multiplier/2.5/select/EUR-USD,1h/output/JSON
```

**Money Flow Index**

The Money Flow Index (MFI) is a technical oscillator that uses both price and volume data to identify overbought or oversold signals in an asset. It oscillates between 0 and 100, typically using levels above 80 to indicate a market top and levels below 20 to indicate a market bottom. Because it incorporates volume, MFI is often considered more reliable than the RSI for spotting "hollow" price moves that lack significant capital backing.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/mfi/period/21/select/BTC-USD,1h/output/JSON
```

**Hull Moving Average**

The Hull Moving Average (HMA) is a high-speed technical indicator designed to eliminate the inherent lag of traditional moving averages while maintaining a smooth, trackable curve. It achieves this by combining multiple Weighted Moving Averages (WMA) and a square root period calculation to stay more closely "glued" to the current price action. Because of its responsiveness, it is highly valued by scalpers and day traders for identifying trend pivots significantly faster than a standard SMA or EMA.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/hma/period/14/select/EUR-USD,1h/output/JSON
```

**Supertrend**

The Supertrend is a trend-following indicator that uses the Average True Range (ATR) to create dynamic support and resistance levels. It simplifies market analysis by providing a single line that flips above or below the price, signaling a change from a bullish to a bearish trend when the candle closes on the opposite side. Because of its mathematical stability, it is widely used as an automated trailing stop-loss that adjusts only in the direction of the trade.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/supertrend/period/10/multiplier/2.0/select/EUR-USD,15m/output/JSON
```

**Schaff trend cycle**

The Schaff Trend Cycle combines the trend-following nature of the MACD with the cyclical accuracy of Stochastics to identify market shifts with minimal lag. It is particularly effective at catching the beginning of a new trend after a period of consolidation, as it remains at 0 or 100 during strong moves and flips quickly when momentum shifts. Traders typically enter long when the STC crosses above 25 and exit or go short when it drops below 75.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/stc/cycle/10/fast/23/slow/50/select/EUR-USD,15m/output/JSON
```

**Fibonacci**

The Fibonacci Retracement indicator identifies potential support and resistance levels by calculating horizontal lines at mathematical ratios—most commonly 23.6%, 38.2%, 50%, 61.8%, and 78.6%—between a significant market high and low. It is based on the theory that after a major price move, the market will frequently "retrace" a predictable portion of that move before resuming its original direction. Traders use these static levels to pinpoint high-probability entry zones, set stop-losses, and establish profit targets.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/fibonacci/period/100/select/EUR-USD,15m/output/JSON
```

**Commodity Channel Index**

The Commodity Channel Index (CCI) measures the current price level relative to an average price level over a specific time period to identify cyclical trends. It typically oscillates between -100 and +100, where values above +100 indicate a strong uptrend (overbought) and values below -100 indicate a strong downtrend (oversold). Traders use these extremes to identify potential exhaustion points or to confirm momentum breakouts when the indicator crosses these key thresholds.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/cci/period/20/select/EUR-USD,15m/output/JSON
```

**Pivot points**

The Pivot Points indicator calculates a central "Pivot" level and multiple support and resistance lines (S1-S3, R1-R3) based on the high, low, and close of a lookback period. These levels serve as psychological price floors and ceilings that remain fixed for the duration of the current session, providing clear targets for profit-taking and stop-loss placement. When used with a trend trigger like the Supertrend, they help traders avoid entering "late" into a trend that is already hitting a major resistance level.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/pivot/period/1/select/EUR-USD,15m/output/JSON
```



**Note:** These are AI generated. Check them thoroughly before you use them. I will check them as soon as V1.1 lands-i can then visualize them more easily.

>While asking an other AI about the code-quality of the other AI: The code quality is excellent - these are well-structured, production-ready implementations. The minor issues noted are mostly cosmetic and don't affect core functionality. The consistent architecture makes maintenance easy and adding new indicators straightforward. The indicators should work correctly for their intended purposes with proper financial data input. A third AI also confirms they are correct. However, i like manual verification. Which will happen just before release of API v1.1.

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

## Thread Safety & Concurrency

Currently, we are running the API requests in a single-threaded event-loop. This is sufficient for most research use-cases (1-5 concurrent users, 20-120 QPS depending on timeframe complexity).

**Expected throughput per timeframe:**
- Weekly/Daily: 90-120 requests/second
- 1-minute data: 20-25 requests/second

We have not programmed for high-concurrency, enterprise-scale environments. If you need the API to handle such environments-NUMA aware, you can contact me via the email address shown in commit messages. Note that I will not support data-distribution environments (paid or unpaid). High performance research environments requiring a scalable HTTP API only.

### Performance Characteristics (typical laptop environment)

| Timeframe | Response Time | Data Coverage (limit=1400) | Primary Use Case |
|-----------|---------------|----------------------------|------------------|
| Weekly (1W) | 8-9ms | ~27 years | Long-term trend analysis |
| Daily (1D) | 10-12ms | ~3.8 years | Position trading |
| Hourly (1H) | 13-15ms | ~58 days | Swing trading |
| 5-Minute (5m) | 22-25ms | ~4.8 days | Day trading |
| 1-Minute (1m) | 45-50ms | ~23 hours | Scalping/backtesting |

**Notes:**
- **Base overhead**: ~8.37ms (HTTP + JSON serialization + event loop + config loading)
- **Config loading**: 3-5ms initial overhead (can benefit from cache optimization)
- **Scaling**: Linear with data density - 1-minute is ~5.5x slower than weekly
- **Concurrent requests**: Process sequentially in single-threaded event loop

**Benchmark Context:**
- Tested on typical laptop hardware (mobile CPU, SSD storage)
- Includes Bollinger Bands calculation (period=20, std=2.0)
- Memory-mapped binary file access for optimal I/O performance


**Theoretical performance thread-optimized version (typical laptop environment, 16 cores)**

| Metric | Single-threaded | 16-Core Optimized | Factor |
| :--- | :--- | :--- | :--- |
| **Throughput (QPS)** | 22 (1m data) | 300–350 | **15x** |
| **Concurrent users** | 5 | 50–80 | **10–16x** |
| **Response time (p95)** | 46ms | 15–20ms | **2–3x faster** |
| **Memory usage** | 50–100MB | 800MB–1.5GB | 8–15x |
