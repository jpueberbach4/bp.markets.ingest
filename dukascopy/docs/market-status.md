# Market Status and Synchronization Indicators

This document outlines the core logic for determining candle finality, feed latency, and system health using a global heartbeat.

---

## 1. `is-open` (Candle Finality)

The `is-open` feature has been redesigned to eliminate a critical bug. It now utilizes a global "Heartbeat" (the BTC-USD 1m market) to determine if a candle is still active or should be considered closed.

### Definitions
* **`global_now_ms`**: The `time_ms` of the latest 1m BTC-USD candle (Global Heartbeat).
* **`tf`**: The currently selected timeframe (e.g., `4h`).
* **`tf_lengths`**: A mapping of timeframe to its duration in milliseconds (e.g., `1h = 3600000`).
* **`last_ms`**: The timestamp of the last candle of the currently selected asset and symbol.

### The Logic
A candle is considered **OPEN** (`is-open = TRUE`) if:

**`last_ms >= (global_now_ms - tf_lengths.get(tf, 0))`**

**Broker Quirk Handling:** For timeframes less than 1 Day, if the asset's 1-minute drift is less than the timeframe duration, the system anchors the is-open boundary to the asset's own latest timestamp rather than the global heartbeat. This ensures non-standard candle lengths (e.g., SGD-IDX 6H30M "H4" candles) are correctly identified as open while the market is active.

See [config/dukascopy/timeframes/indices/SGD-indices.yaml](../config/dukascopy/timeframes/indices/SGD-indices.yaml) (merge logic).

### Implications
If an asset stops ticking (no new data arrives) while data continues to flow for BTC-USD, the asset's last candle will be marked **CLOSED** as soon as the global heartbeat moves past the candle's expected duration. This ensures that stale data is not indefinitely treated as an active "live" candle.


---

## 2. `drift` (Market Latency)

The `drift` indicator measures the synchronization gap between the current asset and the global market.

* **Behavior**: Outputs the difference in **minutes** between the selected asset's latest 1m candle and the last 1m BTC-USD candle.
* **Availability**: Currently available in the `main` branch.
* **Use Case**: Essential for identifying assets lagging behind the global market due to liquidity issues, session closures, or provider delays.

---

## 3. `is-stale(tolerance)` (System Health)

While `drift` compares two markets, `is-stale` compares the market feed against **local system time**.

* **Behavior**: Outputs a boolean flag indicating if a market has failed to receive any data for a period exceeding the user-defined `tolerance`.
* **Comparison**: Calculated relative to the **laptop-time** (wall-clock time).
* **Use Case**: This is used to detect local connectivity issues, process hangs, or API outages that are independent of market behavior.

---

## Summary Comparison

| Indicator | Comparison | Primary Purpose |
| :--- | :--- | :--- |
| **`is-open`** | Asset vs. Global Heartbeat | Determines if a candle is final/settled. |
| **`drift`** | Asset vs. Global Heartbeat | Measures market-to-market synchronization (Minutes). |
| **`is-stale`** | Asset vs. System Clock | Detects local process or connectivity failure. |

## Important example

Take SGD-IDX:

- The last 4H candle opened at 19:51.
- The last 1m candle for SGD-IDX is at 22:59.
- The last 1m BTC-USD candle (global reference) is at 02:11.

This results in a drift of 192 minutes.

Even though the drift (192) is less than the length of H4, the 4H candle is closed — and this is correct.

Why?

Because the last 1m candle at 22:59 still belongs to the 4H candle that started at 19:51. That 4H window has already completed relative to the global reference time.

So don’t misinterpret the drift value in isolation.

The candle boundaries are determined by the timeframe window — not just by the drift number.