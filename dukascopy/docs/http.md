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
`http://localhost:8000/ohlcv/1.0/`
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

Serial execution mode:

> Serial execution mode passes the output of the first indicator into the second, the outputs of the first and second into the third, and so on. While not yet supported, this feature is coming soon. \
\
The goal is to enable ordered chaining of system indicators, where all preceding indicator outputs are fed into a custom indicator. This allows the custom indicator to operate on all generated columns efficiently and in a fully vectorized way, without leaving main memory or triggering recomputation. \
\
In effect, this provides pipelining within a single HTTP API request, with minimal additional effort. Virtual indicators will also be supported, allowing you to configure an indicator chain and assign it a virtual ID. That virtual ID is expanded and resolved at request time.

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

General advice: use the integrated indicator endpoint in API-version 1.1. V1.0 is supported as seen as a "legacy" implementation.

### Custom indicators

Are supported. See [here](indicators.md) for more information.

### Indicator list

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
GET http://localhost:8000/ohlcv/1.0/indicator/pivot/lookback/1/select/EUR-USD,15m/output/JSON
```

**Williams %r**

Williams %R is a momentum indicator that measures overbought and oversold levels by comparing an asset's closing price to its high-low range over a specific period, typically 14 days. The indicator oscillates between 0 and -100, where readings from 0 to -20 are considered overbought and -80 to -100 are considered oversold. It is technically an inverse of the Fast Stochastic Oscillator, reflecting the relationship of the close to the highest high of the lookback window.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/williamsr/after/2026-01-01+00:00:00/select/BTC-USD,15m/period/14/output/JSON?order=desc&limit=400
```

**Standard Deviation**

Standard Deviation is a statistical measure of market volatility that quantifies how much prices are dispersed from their average (mean) value. In trading, a high standard deviation indicates high volatility and significant price swings, while a low standard deviation suggests a stable, consolidating market. It is most commonly used as the foundational component for other indicators like Bollinger Bands to identify extreme price movements.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/stddev/after/2026-01-01+00:00:00/select/BTC-USD,15m/period/20/output/JSON?order=desc&limit=400
```

**Donchian Channels**

Donchian Channels consist of three lines generated by moving average calculations that form an envelope around price. The upper band marks the highest high of the last N periods, the lower band marks the lowest low of the last $N$ periods, and the middle line is the average of the two. This indicator is primarily used to identify breakouts and measure market volatility based on price extremes.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/donchian/after/2026-01-01+00:00:00/select/BTC-USD,15m/period/20/output/JSON?order=desc&limit=400
```

**Ichimoku Cloud**

The Ichimoku Cloud is a comprehensive technical indicator that provides a holistic view of market trend, momentum, and dynamic support and resistance levels through a single integrated system. It consists of five primary lines—the Tenkan-sen, Kijun-sen, Senkou Span A, Senkou Span B, and Chikou Span—which collectively create a "cloud" (Kumo) that helps traders identify price direction and future barriers at a glance. By projecting certain components into the future and shifting others into the past, it offers a multi-dimensional perspective that distinguishes it from standard moving averages.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/ichimoku/after/2026-01-01+00:00:00/select/BTC-USD,15m/tenkan/9/kijun/26/senkou_b/52/displacement/26/output/JSON?order=desc&limit=1000
```

**Rate Of Change**

The Rate of Change (ROC) is a pure momentum oscillator that measures the percentage change between the current price and the price a specific number of periods ago. It oscillates around a zero line, where positive values indicate an upward trend with increasing momentum and negative values signal a downward trend. Because it compares price to a fixed historical point, it is highly effective at identifying overbought or oversold conditions and potential trend reversals through divergences.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/roc/after/2026-01-01+00:00:00/select/BTC-USD,15m/period/12/output/JSON?order=desc&limit=400
```

**On-Balance Volume**

On-Balance Volume (OBV) is a cumulative momentum indicator that uses volume flow to predict changes in stock price. It operates on the principle that volume precedes price movement: if the current close is higher than the previous close, the volume is added to the OBV; if the current close is lower, it is subtracted.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/obv/after/2026-01-01+00:00:00/select/BTC-USD,15m/output/JSON?order=desc&limit=400
```

**Chande Momentum Oscillator**

The Chande Momentum Oscillator (CMO) is a technical momentum indicator developed by Tushar Chande that measures the relative strength or weakness of a market by comparing the sum of all recent gains to the sum of all recent losses over a specific timeframe. It oscillates between -100 and +100, where values above +50 typically indicate overbought conditions and values below -50 suggest oversold conditions. Unlike other oscillators like the RSI, the CMO uses unsmoothed data in its primary calculation, making it highly sensitive to short-term price shifts and effective for identifying trend strength and potential price reversals.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/cmo/after/2026-01-01+00:00:00/select/BTC-USD,15m/period/14/output/JSON?order=desc&limit=400
```

**Elder Ray Index**

The Elder Ray Index, also known as Bull and Bear Power, is a trend-following indicator developed by Dr. Alexander Elder that measures the strength of buying and selling pressure relative to a baseline. It consists of two separate oscillators: Bull Power, calculated as the period's high minus an Exponential Moving Average (EMA), and Bear Power, calculated as the low minus the same EMA. Traders use it to "see through" price action like an X-ray, identifying when bulls or bears are gaining control or when divergences suggest an upcoming trend reversal.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/elderray/period/13/after/2026-01-01+00:00:00/select/BTC-USD,15m/output/JSON?order=desc&limit=400
```

**Detrended Price Oscillator**

The Detrended Price Oscillator (DPO) is an indicator designed to filter out long-term trends in order to identify cyclical patterns and overbought/oversold levels. It achieves this by comparing the closing price to a Simple Moving Average (SMA) that has been shifted back in time by half the lookback period. Because it highlights the distance between price and its displaced average, it allows traders to estimate the duration of price cycles from peak to peak or trough to trough.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/dpo/period/20/after/2026-01-01+00:00:00/select/BTC-USD,15m/output/JSON?order=desc&limit=400
```

**KDJ**

The KDJ Indicator is a trend-following and momentum oscillator consisting of three lines—K, D, and J—that fluctuate between 0 and 100 to signal overbought or oversold conditions. While the K and D lines represent the standard stochastic values, the J line is a divergent line calculated as the difference between the other two, often used to highlight extreme price deviations. Traders look for "Golden Crosses" (bullish) and "Dead Crosses" (bearish) when these lines intersect, particularly in areas of market exhaustion.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/kdj/n/9/m1/3/m2/3/after/2026-01-01+00:00:00/select/BTC-USD,15m/output/JSON?order=desc&limit=400
```

**Aroon**

The Aroon Indicator measures the time between highs and lows over a specific period to determine if a trend is starting, ending, or consolidating. Aroon Up tracks the strength of the uptrend by looking at how long it has been since the last 25-period high, while Aroon Down tracks the downtrend by measuring the time since the last 25-period low. When Aroon Up is near 100 and Aroon Down is near 0, a strong uptrend is confirmed, whereas crossovers between the two lines often signal potential trend reversals.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/aroon/period/25/after/2026-01-01+00:00:00/select/BTC-USD,15m/output/JSON?order=desc&limit=400
```

**Ultimate Oscillator**

The Ultimate Oscillator uses a weighted sum of three different timeframes (typically 7, 14, and 28 periods) to measure buying pressure relative to the true range of price movement. It oscillates between 0 and 100, where values above 70 indicate overbought conditions and values below 30 suggest the market is oversold. Traders primarily look for bullish or bearish divergences between the oscillator and the price action to identify potential trend reversals.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/uo/p1/7/p2/14/p3/28/after/2026-01-01+00:00:00/select/BTC-USD,15m/output/JSON?order=desc&limit=400
```

**Chaikin Oscillator**

The Chaikin Oscillator applies the MACD concept to the Accumulation Distribution Line by calculating the difference between a 3-day EMA and a 10-day EMA of the ADL. It helps traders identify shifts in market momentum and buying/selling pressure before those changes are reflected in the asset's price. A reading above zero indicates accumulation and positive momentum, while a reading below zero suggests distribution and negative momentum.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/chaikin/short/3/long/10/after/2024-01-01+00:00:00/select/BTC-USD,1d/output/JSON?order=desc&limit=400
```

**Accumulation/Distribution Line**

The Accumulation/Distribution Line is a cumulative indicator that uses price and volume to assess whether an asset is being accumulated or distributed. It calculates a Money Flow Multiplier based on where the price closes within its daily range and multiplies this by volume to create a running total. Traders primarily use the ADL to confirm trends or identify potential reversals through divergences, such as when price makes a new high but the ADL fails to follow.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/adl/after/2026-01-01+00:00:00/select/BTC-USD,1d/output/JSON?order=desc&limit=400
```

**Renko**

Renko charts are a unique technical analysis tool that ignores time entirely and focuses exclusively on significant price movements. They are constructed using "bricks" of a fixed size, where a new brick is only added at a 45-degree angle if the price moves a predetermined amount (the Brick Size) from the previous brick's close. This method effectively filters out market noise and minor fluctuations, making it significantly easier for traders to identify clear trends, support/resistance levels, and major reversals.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/renko/after/2026-01-01+00:00:00/select/BTC-USD,1m/brick_size/50/output/JSON?order=desc&limit=400
```

**Heikin Ashi**

Heikin Ashi (meaning "average bar" in Japanese) is a modified candlestick technique that smooths price action by averaging current data with the previous candle's values. It eliminates the "gaps" found in traditional charts and helps traders stay in trends longer by coloring candles consistently during bullish or bearish runs. While easier to read for trend identification, it is a lagging indicator and does not show exact market execution prices.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/heikinashi/after/2026-01-01+00:00:00/select/BTC-USD,1m/output/JSON?order=desc&limit=5000
```

**Point & Figure**

Point & Figure (P&F) charting is a technical analysis technique that filters out "noise" by only recording price changes and ignoring time and volume. It consists of columns of X's (rising prices) and O's (falling prices), where a new column is only started when the price reverses by a specific number of boxes—most commonly three. This allows traders to clearly visualize long-term trend lines, identify break-out patterns, and determine precise price targets regardless of how long it takes for the market to move.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/pointfigure/after/2026-01-01+00:00:00/select/BTC-USD,1m/box_size/100/reversal/3/output/JSON?order=desc&limit=5000
```

**Kagi Chart**

A Kagi chart is a time-independent technical analysis tool that uses a single continuous line to track price movements and filter out minor market noise. The line shifts between "Yang" (thick) and "Yin" (thin) states to signal trend changes: a thick Yang line appears when the price breaks above a previous peak (shoulder), while a thin Yin line appears when it breaks below a previous trough (waist). Traders primarily use Kagi charts to identify the underlying supply-and-demand balance, entering long positions when the line turns thick and exiting when it turns thin.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/kagi/after/2026-01-01+00:00:00/select/BTC-USD,1m/reversal/100/mode/fixed/output/JSON?order=desc&limit=5000
```

**The Three Line Break**

The Three Line Break (TLB) chart is a trend-following technique that filters out minor price fluctuations by only adding lines when the market reaches new highs or lows. Its defining characteristic is the reversal rule: if the current trend has produced three or more consecutive lines in the same direction, the price must close beyond the extreme high or low of those last three lines to trigger a reversal in the opposite direction. This delay in signaling reversals makes TLB charts excellent for identifying high-conviction trend changes while keeping traders away from "choppy" lateral markets.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/threelinebreak/after/2026-01-01+00:00:00/select/BTC-USD,1m/break/3/output/JSON?order=desc&limit=5000
```

**Z-score**

The Z-Score is a statistical momentum indicator that quantifies how "extreme" a price move is by measuring its distance from the mean in units of standard deviation. In a normal distribution, approximately 95% of price action stays within a Z-Score range of -2.0 to +2.0; therefore, when the score exceeds these levels, it often signals a high probability of a mean-reversion trade. Unlike the RSI, which is bound between 0 and 100, the Z-Score is "unbound," allowing it to show the true intensity of a trend or a volatility spike without being dampened by a fixed scale.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/zscore/after/2026-01-01+00:00:00/select/BTC-USD,1m/period/20/output/JSON?order=desc&limit=5000
```

**Hurst Exponent**

The Hurst Exponent is a statistical measure used to quantify the "long-term memory" of a time series, helping traders determine the hidden nature of market volatility. It produces a value between 0 and 1: a value of 0.5 indicates a completely random market (Brownian motion), while values above 0.5 indicate a persistent, trending market where price increases are likely to follow price increases. Conversely, a value below 0.5 indicates an anti-persistent or mean-reverting market, where the price is likely to reverse its current direction, making it an essential tool for choosing between trend-following or mean-reversion strategies.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/hurst/after/2026-01-01+00:00:00/select/BTC-USD,1m/period/100/output/JSON?order=desc&limit=1000
```

**Fractal Dimension**

The Fractal Dimension (D) is a measure of the geometric complexity of a price chart, describing how "fragmented" the price movement is across a given period. In trading, a value near 1.0 suggests a highly efficient, linear trend where price is moving directly toward a target, while a value approaching 2.0 indicates extreme "choppiness" or noise where the price path is essentially filling a 2D area. By monitoring the Fractal Dimension, traders can identify when a trend is beginning to break down into chaos (D increases) or when a period of consolidation is beginning to organize into a new, efficient trend (D decreases).

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/fractaldimension/after/2026-01-01+00:00:00/select/BTC-USD,1m/period/30/output/JSON?order=desc&limit=1000
```

**Shannon Entropy**

Shannon Entropy is a mathematical concept from information theory that quantifies the "information density" or degree of randomness within a dataset. In financial markets, it is used to measure the complexity of price action: low entropy values indicate that the market is in a highly structured state, such as a strong trend where price movements are predictable and "orderly." Conversely, high entropy values suggest that the market is in a state of maximum uncertainty or "noise," typical of sideways consolidation or volatile "choppiness" where the next price move is statistically harder to predict.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/shannonentropy/after/2026-01-01+00:00:00/select/BTC-USD,1m/period/20/bins/10/output/JSON?order=desc&limit=1000
```

**Linear Regression Channel**

The Linear Regression Channel is a three-line technical indicator that uses statistical analysis to determine the trend and volatility of an asset over a specific period. The middle line, known as the Linear Regression Line, is the "best fit" path that minimizes the distance between itself and all price points in the window. The Upper and Lower Channels are drawn parallel to this line, usually based on the maximum distance price has deviated from the trend (or a multiple of standard deviation). When price hits the outer bands, it is often considered "overextended" and statistically likely to revert back toward the middle regression line, making it a powerful tool for identifying both the trend direction and potential reversal points.

```sh
GET http://localhost:8000/ohlcv/1.0/indicator/linregchannel/after/2026-01-01+00:00:00/select/BTC-USD,1m/period/50/output/JSON?order=desc&limit=1000
```


**Note:** Most indicators have been generated by AI by have been checked and confirmed to be working correctly. However, some indicators, those with "verified:0" in the meta flags are known to be problematic. These will be removed from the code base. Do not use them. Other indicators will replace them. Example cross-asset indicators will be added. Eg a Pearson correlation indicator between BUND and EUR-USD.

**Note:** Added a small helper script to generate indicator output to CSV. `http://localhost:8000/indicator.html`

>While asking an other AI about the code-quality of the other AI: The code quality is excellent - these are well-structured, production-ready 

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

**Note:** These are old performance characteristics, since then things have improved.

**Note:** Endpoint has been hammered with 100.000 heavy query requests overnight. 0 failures. Very stable.

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

| Metric | Single-threaded | 16-Core Optimized | Factor | Kubernetes |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (QPS)** | 22 (1m data) | 300–350 | **15x** | Virtually unlimited |
| **Concurrent users** | 5 | 50–80 | **10–16x** | Virtually unlimited |
| **Response time (p95)** | 46ms | 15–20ms | **2–3x faster** | Same base stats |
| **Memory usage** | 50–100MB | 800MB–1.5GB | 8–15x | 1024MB per pod |
