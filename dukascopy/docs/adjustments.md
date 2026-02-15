# Developer's Guide: Custom Back-Adjustment Strategies

This guide outlines how to implement custom **Back-Adjustment Strategies** for the `generators.sidetracking` module. This system allows you to create "Sidetracked" symbols (e.g., `AAPL.US-USD-ADJUSTED` or `BRENT.CMD-USD-PANAMA`) that exist in parallel to your raw broker data, providing a clean, continuous price history for backtesting and analysis.

The system supports three primary adjustment methodologies:

1.  **Futures Panama:** Subtractive rollover adjustment (for Commodities/Indices).
2.  **Standard Corporate Actions:** Hybrid adjustment (Subtractive Dividends, Multiplicative Splits).
3.  **Total Return (Ratio):** Pure Multiplicative adjustment (Ratio-based Dividends to prevent negative prices).

---

## 1. The Interface: `IAdjustmentStrategy`

All strategies must implement the `IAdjustmentStrategy` interface. The pipeline relies on two methods: `fetch_data` to get the raw events, and `generate_config` to turn those events into linear, non-overlapping time-window instructions.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class TimeWindowAction:
    """
    Defines a specific adjustment to be applied to a time window.
    """
    id: str             # Unique identifier (e.g., "div-20200831")
    action: str         # Operator: "+" (add), "-" (sub), "*" (mul), "/" (div)
    columns: List[str]  # Columns to apply to (e.g., ["open", "close"])
    value: float        # The adjustment value
    from_date: datetime # Window Start (Inclusive)
    to_date: datetime   # Window End (Inclusive)

class IAdjustmentStrategy:
    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Scrapes or fetches raw corporate action/rollover events.
        Returns a list of raw event dictionaries (schema is up to you).
        """
        pass

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        """
        Converts raw events into a list of linearized TimeWindowActions.
        Crucial: Windows must NOT overlap.
        """
        pass
```

## 2. Strategy Type A: Futures Panama (Rollover Adjustment)

Use Case: Continuous Futures contracts (e.g., Brent, WTI, Indices).

Method: Subtractive. We accumulate the "Rollover Gap" and shift historical prices to align with the current front-month contract.

Logic: Reverse Accumulation. Start from "Today" (0 offset) and work backward.

Implementation Pattern: `DukascopyPanamaStrategy`

```python
class DukascopyPanamaStrategy(IAdjustmentStrategy):
    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        # ... (Implementation details: Fetches JSON from Dukascopy API) ...
        # Returns: [{'date': '2023-12-15', 'gap': -0.45}, ...]
        pass

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        # Sort by Date Ascending first to sum total gap
        raw_data.sort(key=lambda x: x['date'])
        
        # Calculate Total Gap (The offset required for the oldest data)
        total_cumulative = sum(e['gap'] for e in raw_data)
        current_offset = total_cumulative
        
        actions = []
        prev_date = datetime(2000, 1, 1)

        # Stitch Windows (Oldest -> Newest)
        for i, event in enumerate(raw_data):
            roll_date = event['date']
            # Window ends at the rollover moment
            window_end = roll_date.replace(hour=23, minute=59, second=59)

            if window_end > prev_date:
                actions.append(TimeWindowAction(
                    id=f"roll-{i}",
                    action="+", # Add the offset to align past with future
                    columns=["open", "high", "low", "close"],
                    value=round(current_offset, 6),
                    from_date=prev_date,
                    to_date=window_end
                ))

            # Step down the offset as we move forward in time
            current_offset -= event['gap']
            
            # Stitch: Next window starts 1 second later
            prev_date = window_end + timedelta(seconds=1)

        return actions
```

## 3. Strategy Type B: Corporate Actions (Standard Panama)

Use Case: Stocks where you want to see absolute price movements but adjust for splits and dividends.

Method: Hybrid. Splits are Multiplicative (*), Dividends are Subtractive (-).

Warning: Can result in negative prices for older data if dividends exceed historical price.

Critical "Plumbing" Details

Stock Splits: Use Payable Date. The split applies to the next trading day.

Dividends: Use Record Date (proxy for Ex-Date). Using Payable Date causes a 2-week lag error.

Implementation Pattern: `AppleCorporateActionsStrategy`

```python
class AppleCorporateActionsStrategy(IAdjustmentStrategy):
    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        # Logic: Scrape Apple IR.
        # If Type == "Stock Split" -> Use Payable Date
        # If Type == "Dividend"    -> Use Record Date
        pass

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        # Sort Newest -> Oldest to accumulate backwards
        raw_data.sort(key=lambda x: x["date"], reverse=True)
        
        segments = []
        cum_split = 1.0
        cum_div = 0.0

        for event in raw_data:
            if "split_factor" in event:
                cum_split *= (1.0 / float(event["split_factor"]))
            elif "dividend" in event:
                # Add dividend adjusted for splits seen so far
                cum_div += (event["dividend"] * cum_split)
            
            segments.append({
                "date": event["date"], 
                "split": cum_split, 
                "div": cum_div,
                "type": "Stock Split" if "split_factor" in event else "Dividend"
            })

        # Linearize (Stitch) Windows Oldest -> Newest
        segments.sort(key=lambda x: x["date"])
        actions = []
        prev_end = datetime(2000, 1, 1)

        for seg in segments:
            # Window End Logic:
            # Split -> Ends ON Payable Date (23:59:59)
            # Div   -> Ends DAY BEFORE Record Date (Record - 1 day)
            if seg["type"] == "Stock Split":
                curr_end = seg["date"].replace(hour=23, minute=59, second=59)
            else:
                curr_end = (seg["date"] - timedelta(days=1)).replace(hour=23, minute=59, second=59)

            if curr_end > prev_end:
                # Emit separate actions for Split (*) and Div (-) for the same window
                if abs(seg["split"] - 1.0) > 1e-9:
                    actions.append(TimeWindowAction(..., action="*", value=seg["split"], ...))
                if abs(seg["div"]) > 1e-9:
                    actions.append(TimeWindowAction(..., action="-", value=seg["div"], ...))
            
            prev_end = curr_end + timedelta(seconds=1)
            
        return actions
```

## 4. Strategy Type C: Corporate Actions (Total Return Ratio)

Use Case: Performance analysis, Algorithms, "Total Return" series.

Method: Pure Multiplicative. Dividends are converted to a ratio: 1 - (Dividend / Price).

Requirement: Requires access to historical price data (api.get_data) to calculate yield.

Key Logic

- No Negative Prices: Price scales down asymptotically toward zero.

- "The Peek": You must query the historical closing price on the Ex-Date to calculate the ratio.

Implementation Pattern: `AppleCorporateActionsStrategyRR`

```python
# Import local API to peek at historical prices
from api import get_data

class AppleCorporateActionsStrategyRR(IAdjustmentStrategy):
    # fetch_data is same as Standard Strategy (uses Record/Payable logic)

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        # 1. Sort Newest -> Oldest
        raw_data.sort(key=lambda x: x["date"], reverse=True)
        
        segments = []
        cum_ratio = 1.0

        for event in raw_data:
            if "split_factor" in event:
                # Split is purely multiplicative (1 / Factor)
                cum_ratio *= (1.0 / float(event["split_factor"]))
            elif "dividend" in event:
                # Dividend is Ratio: (1 - Div / Price)
                # Fetch price from day before Record Date
                price = get_data(..., limit=1, ...)
                div_ratio = 1.0 - (event["dividend"] / price)
                cum_ratio *= div_ratio

            segments.append({"date": event["date"], "ratio": cum_ratio, ...})

        # 2. Linearize Windows Oldest -> Newest
        segments.sort(key=lambda x: x["date"])
        actions = []
        prev_end = datetime(2000, 1, 1)

        for seg in segments:
            # Same Window End logic as Standard Strategy
            # ...
            
            # Emit SINGLE Multiplicative Action (*)
            if curr_end > prev_end:
                 actions.append(TimeWindowAction(..., action="*", value=seg["ratio"], ...))

            prev_end = curr_end + timedelta(seconds=1)

        return actions
```

## 5. Panama-RR Hybrid Adjustment Output

This section outlines the logic and structure for the Panama-RR adjustment method. This specific implementation is a "hybrid" model: it utilizes multiplication for structural events (splits) to maintain geometric consistency, and subtraction (Panama method) for cash events (dividends) to maintain point-value consistency.

### 1. Data Structure Overview
The output utilizes YAML Anchors (&id001) and Aliases (*id001) to maintain a DRY (Don't Repeat Yourself) configuration.

- Source: The raw, unadjusted ticker symbol.

- Post-Processing (post): A chronological list of segments (seg-) representing time windows between corporate actions.

- Actions:

  - action: `'*'` : Used for Stock Splits. Multiplies historical OHLC data by the value.

  - action: `'-'` : Used for Dividends (Panama). Subtracts the value from historical OHLC data.


### 2. The Hybrid Logic Flow

When your ingestion engine processes this YAML, it applies adjustments backwards from the current date.

#### Structural Scaling (Splits)

For splits, we use the Ratio method.

**Logic:** `Price_adj = Price_raw * 0.25`

Reasoning: A 4-for-1 split fundamentally changes the "meaning" of a single share. To compare a 1988 candle to a 2026 candle, the 1988 price must be scaled down to modern "share units."

#### Cash Leveling (Panama Dividends)

For dividends in this specific set, we use the Panama method.

**Logic:** `Price_adj = Price_raw - 8.69`

Reasoning: This treats the dividend as a raw cash extraction. It keeps the "gap" in the chart equal to the actual cash paid out, rather than a percentage of the stock price at the time.

### 3. Example
```sh
AAPL.US-USD-PANAMA:
  source: AAPL.US-USD
  post:
    seg-split-19880520:
      action: '*'
      columns: &id001
      - open
      - high
      - low
      - close
      value: 0.25
      from_date: '1987-05-15 00:00:00'
      to_date: '1988-05-19 23:59:59'
      ...
    seg-div-20200210:
      action: '-'
      columns: *id001                       # This is a reference to &id001
      value: 5.8125
      from_date: '2019-11-11 00:00:00'
      to_date: '2020-02-09 23:59:59'
    seg-split-20200511:
      action: '*'
      columns: *id001
      value: 0.25                           # 4 for 1 stocksplit, 1/4 = 0.25
      from_date: '2020-02-10 00:00:00'
      to_date: '2020-05-10 23:59:59'
    seg-div-20200511:
      action: '-'
      columns: *id001                       # This is a reference to &id001
      value: 5.62
      from_date: '2020-02-10 00:00:00'
      to_date: '2020-05-10 23:59:59'
      ...
```

The following example-code retrieves a webpages from investor.apple.com, extracts the mentioned dividend and stocksplit dates with their respective values. Builds an internal table and applies cumulative subtraction and, in case of stocksplits, a multiplication (1 divided by number stocksplut) for each window. Windows are stitched together:

[Example AAPL](../generators/sidetracking/extensions/stocks/apple.py) (class `AppleCorporateActionsStrategy`)

Similarly, for futures, we apply a cumulative subtraction on each rollover date:

[Example futures](../generators/sidetracking/extensions/dukascopy.py) (class `DukascopyPanamaStrategy`)

#### Field descriptions

| Field                 | Developer Note |
|----------------------|----------------|
| columns              | Standardizes adjustments across open, high, low, and close. This ensures the entire candle is shifted or scaled as a single unit, preventing "broken" candles (e.g., where a High could mathematically end up lower than a Close after an adjustment). |
| value drift          | Notice the seg-div values decrease over time (e.g., 8.69 in 1988 vs 0.26 in 2026). This reflects the cumulative "debt" of dividends being removed as you move closer to the present. The further back you go in the time series, the larger the total subtraction applied to the historical data. |
| from_date / to_date  | These define strict inclusive windows. Your SQL or Memory-Sink query must ensure no overlap in the date ranges, or the system will double-adjust prices, leading to significant data corruption and skewed backtesting results. |
