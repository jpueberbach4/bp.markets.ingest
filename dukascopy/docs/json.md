# API 1.1 Developer's Guide: OHLCV JSON Subformats

This guide defines the four available JSON subformats in API 1.1. These formats allow developers to choose the optimal balance between human readability, data density, and streaming performance.

### Base Request URL
`http://localhost:8000/ohlcv/1.1/select/{SYMBOL},{TF}[{INDICATORS}]/after/{TIMESTAMP}/output/JSON?subformat={ID}`

---

## 1. Subformat 1: Record-Oriented JSON (Default)
**Use Case:** Debugging, small datasets, and general-purpose integration.
Each data point is an object with explicit keys.

* **URL Parameter:** `subformat=1`
* **Time Format:** ISO 8601 String.
* **Structure:** Nested `indicators` object per record.

```json
{
  "status": "ok",
  "options": { "subformat": 1, ... },
  "result": [
    {
      "symbol": "AAPL.US-USD",
      "time": "2025-04-24 13:30:00",
      "open": 204.687,
      "indicators": {
        "macd_12_6_9": { "hist": 0.1284, "macd": 0.0273, "signal": -0.101 },
        "sma_9": 204.9919
      }
    }
  ]
}
```

## 2. Subformat 2: Intermediate Columnar JSON

Use Case: Table-based views and internal data processing where headers are needed once.  Data is split into a list of column names and a 2D array of values.

* **URL Parameter:** `subformat=2`
* **Time Format:** Epoch milliseconds.
* **Structure:** Metadata is separated from the raw values to reduce payload size.

```json
{
  "status": "ok",
  "columns": ["symbol", "time", "open", "high", "low", "close", "volume", "indicators"],
  "values": [
    ["AAPL.US-USD", 1745501400000, 204.687, 205.266, 204.566, 204.696, 2.076, {"sma_9": 204.9919, ...}]
  ]
}
```

## 3. Subformat 3: Timeseries Optimized (Flattened)

Use Case: High-performance charting (e.g., Lightweight Charts) and algorithmic analysis.  This is the most efficient non-streaming format. Indicators are flattened into top-level arrays. 

* **URL Parameter:** `subformat=3`
* **Time Format:** Epoch milliseconds.
* **Structure:** Timeseries optimized.
* **Key Feature:** All indicators are flattened using the indicator_name__sub-value convention (e.g., macd_12_6_9__hist).

```json
{
  "status": "ok",
  "columns": ["time", "open", "high", "low", "close", "volume", "macd_12_6_9__hist", "sma_9", ...],
  "result": {
    "time": [1745501400000, 1745501460000],
    "open": [204.687, 204.707],
    ...
    "sma_9": [204.9919, 204.9719]
  }
}
```

## 4. Subformat 4: NDJSON (Newline Delimited / Streaming)

Use Case: Mass data transfer (80,000+ records) and real-time "firehose" feeds. Every line is a standalone JSON object. 

* **URL Parameter:** `subformat=4`
* **Time Format:** Contains both ISO 8601 string AND sort_key (Epoch MS).
* **Structure:** Streaming optimized.
* **Key Feature:** No outer wrapper. Clients can parse line-by-line before the full transfer completes.

```json
{"symbol":"AAPL.US-USD","time":"2025-04-24 13:30:00","sort_key":1745501400000,"open":204.687,...}
{"symbol":"AAPL.US-USD","time":"2025-04-24 13:31:00","sort_key":1745501460000,"open":204.707,...}
```

## Performance overhead

### Comparison Matrix

| Feature | Subformat 1 | Subformat 2 | Subformat 3 | Subformat 4 |
| :--- | :--- | :--- | :--- | :--- |
| **Parsing Effort** | Low | Medium | Very Low (Charts) | Medium (Stream) |
| **Payload Size** | Largest | Medium | Small | Small |
| **Indicator Mode** | Nested Object | Nested Object | **Flattened Array** | Nested Object |
| **Timestamp** | ISO String | Epoch MS | Epoch MS | Both |
| **Streaming** | No | No | No | **Yes** |


## Quick Format Selector

| Use Case | Format | Why |
|----------|--------|-----|
| **Debugging / Testing** | 1 | Human-readable, nested structure |
| **Excel / Table Import** | 2 | Column headers, compact |
| **High-Performance Charts** | 3 | Flattened arrays, fastest rendering |
| **Large Data Export (>10k rows)** | 4 | Streaming, memory efficient |