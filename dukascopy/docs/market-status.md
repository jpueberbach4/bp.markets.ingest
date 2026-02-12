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