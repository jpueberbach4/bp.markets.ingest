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
