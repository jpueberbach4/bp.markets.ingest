#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        dukascopy_panama.py
Author:      JP Ueberbach
Created:     2025-02-14

Purpose:
    Implements a Panama-style back-adjustment strategy using official
    rollover (monthly adjustment) data published by Dukascopy.

    The strategy fetches historical rollover gaps directly from Dukascopy
    and converts them into cumulative time-window adjustments suitable
    for back-adjusting continuous futures or CFD price series.

    This module exists to:
        - Eliminate reliance on paid market data vendors
        - Provide full transparency into rollover mechanics
        - Make historical back-adjustments deterministic and auditable
        - Prove that rollover data is neither proprietary nor complex

Design Notes:
    - Uses Dukascopy's public rollover calendar endpoint
    - Supports JSONP and raw JSON payloads
    - Implements classic Panama back-adjustment logic
    - Produces forward-only, non-overlapping adjustment windows
    - Designed to plug into the generic IAdjustmentStrategy interface

What This Module Does NOT Do:
    - Does NOT download candles or ticks
    - Does NOT modify raw price data directly
    - Does NOT perform symbol discovery
    - Does NOT infer roll dates heuristically
    - Does NOT apply business logic outside of pure adjustment math

Algorithm Summary (Panama Method):
    1. Collect all historical rollover gaps
    2. Apply the full cumulative offset to the oldest data
    3. Step forward in time, subtracting each rollover gap
    4. Emit time windows with monotonically decreasing offsets

Complexity:
    - Normalization: O(N)
    - Sorting rollovers: O(N log N)
    - Window generation: O(N)
    - Total complexity: O(N log N)

Requirements:
    - Python 3.8+
    - requests
    - Standard library only (json, datetime, re)

License:
    MIT License
===============================================================================
"""
from generators.sidetracking.base import IAdjustmentStrategy, TimeWindowAction
from typing import List, Dict, Any
from datetime import datetime, timedelta
from util.api import get_data
import requests
import json
import re


class DukascopyPanamaStrategy(IAdjustmentStrategy):
    # Constant URL → lookup is O(1)
    BASE_URL = "https://freeserv.dukascopy.com/2.0/"
    
    def __init__(self):
        """Initializes the strategy configuration.

        Sets the expected date format used by Dukascopy payloads and defines
        the OHLC columns that will be adjusted during back-adjustment.
        """
        # Date format used by Dukascopy CSV/JSON payloads → O(1)
        self.csv_date_fmt = "%d-%b-%y"

        # OHLC columns to adjust → small fixed list → O(1)
        self.target_columns = ["open", "high", "low", "close"]

    def _normalize_payload(self, data: str, symbol: str) -> List[Dict[str, Any]]:
        """Normalizes the raw Dukascopy API response.

        This method unwraps JSONP responses, parses JSON content, converts
        symbol formats, and filters rows to only include entries relevant
        to the requested trading symbol.

        Args:
            data: Raw response text returned by the Dukascopy API.
            symbol: Internal symbol identifier (e.g. "BRENT.CMD-USD").

        Returns:
            A list of dictionaries containing normalized rollover data
            for the specified symbol.
        """
        # Trim whitespace from the response string → O(N)
        data = data.strip()

        # Detect JSONP wrapper (Dukascopy uses this sometimes)
        # startswith check → O(1)
        if data.startswith("_callbacks____qmjn9av6ydd"):
            # Regex search over entire payload → O(N)
            match = re.search(r"_callbacks____qmjn9av6ydd\((.*)\)", data, re.DOTALL)
            if match:
                # Extract the JSON payload → O(1)
                data = match.group(1)
            else:
                # No usable payload → O(1)
                return []

        try:
            # Parse JSON string into Python objects → O(N)
            json_data = json.loads(data)
        except json.JSONDecodeError as e:
            # Bubble up parsing errors → O(1)
            raise e

        # Empty response guard → O(1)
        if not json_data:
            return []

        # Convert symbol format (e.g. BRENT.CMD-USD → BRENT.CMD/USD)
        # String ops are proportional to symbol length → O(1)
        api_symbol = "/".join(symbol.rsplit("-", 1))

        # Filter only rows matching the requested symbol
        # Iterates over all rows → O(N)
        filtered_rows = [
            row for row in json_data
            if str(row.get("title", "")).strip().casefold()
            == api_symbol.strip().casefold()
        ]

        # Return only relevant rows → O(1)
        return filtered_rows

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetches rollover adjustment data from Dukascopy.

        Performs an HTTP GET request using the expected headers and query
        parameters, then normalizes the returned payload.

        Args:
            symbol: Internal symbol identifier to fetch rollover data for.

        Returns:
            A list of dictionaries containing normalized rollover data.
            Returns an empty list if the request fails.
        """
        # User feedback only → O(1)
        print(f"[*] Fetching remote data for {symbol}...")
        
        # Static HTTP headers → O(1)
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "referer": "https://freeserv.dukascopy.com/2.0/?path=cfd_monthly_adjustment/index&header=false",
        }

        # Static query params → O(1)
        params = {
            "path": "cfd_monthly_adjustment/getData",
            "start": "0000000000000",
            "end": "2006745599999",
            "jp": "0",
            "jsonp": "_callbacks____qmjn9av6ydd",
        }

        try:
            # HTTP request → network-bound, not algorithmic
            response = requests.get(
                self.BASE_URL,
                headers=headers,
                params=params,
                timeout=15
            )

            # Status check → O(1)
            response.raise_for_status()
            
            # Normalize and filter payload → O(N)
            return self._normalize_payload(response.text, symbol)

        except requests.RequestException as e:
            # Handle network errors gracefully → O(1)
            raise Exception(f"[!] Network error fetching data: {e}")

    def generate_config(
        self,
        symbol: str,
        raw_data: List[Dict[str, Any]]
    ) -> List[TimeWindowAction]:
        """Generates back-adjustment windows using the Panama method.

        Converts rollover events into cumulative back-adjustment time windows
        by applying the total offset to historical data and decrementing it
        at each rollover boundary.

        Args:
            symbol: Internal symbol identifier (unused but kept for interface consistency).
            raw_data: Normalized rollover data as returned by `fetch_data`.

        Returns:
            A list of TimeWindowAction objects defining adjustment windows.
        """
        # No data → nothing to do → O(1)
        if not raw_data:
            return []

        events = []

        # Parse raw rows into (date, gap) pairs
        # Single pass over input → O(N)
        for row in raw_data:
            if not row.get('date') or row.get('short') is None:
                continue
            try:
                # Parse date string → O(1)
                dt = datetime.strptime(row['date'], self.csv_date_fmt)

                # Convert gap to float → O(1)
                gap = float(row['short'])

                # Store normalized event → O(1)
                events.append({'date': dt, 'gap': gap})
            except ValueError:
                continue

        # Sort rollover events by date
        # Sorting dominates runtime → O(N log N)
        events.sort(key=lambda x: x['date'])

        # Sum all gaps to compute total back-adjustment
        # Single pass → O(N)
        total_cumulative = sum(e['gap'] for e in events)

        # Current offset starts at full cumulative adjustment → O(1)
        current_offset = total_cumulative
        
        actions = []

        # Fixed artificial start date → O(1)
        prev_date = datetime(2000, 1, 1, 0, 0, 0)

        # Generate adjustment windows
        # Iterates once per rollover event → O(N)
        for i, event in enumerate(events):
            roll_date = event['date']

            # Window ends at end of rollover day → O(1)
            window_end = roll_date.replace(hour=23, minute=59, second=59)

            # Only create valid forward-moving windows → O(1)
            if window_end > prev_date:
                action = TimeWindowAction(
                    id=f"panama-roll-{i+1:03d}",
                    action="+",
                    columns=list(self.target_columns),
                    value=round(current_offset, 6),
                    from_date=prev_date,
                    to_date=window_end
                )
                actions.append(action)

            # Remove this rollover’s gap for future windows → O(1)
            current_offset -= event['gap']

            # Next window starts the day after rollover → O(1)
            prev_date = (roll_date + timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )

        # Return final list of adjustment actions → O(1)
        return actions
    

# ----- RETURN RATIO STRATEGY - SIMPLIFIED - NO NEGATIVE PRICES -----

class DukascopyPanamaStrategyRR(IAdjustmentStrategy):
    """
    Ratio-based (Multiplicative) Futures Back-Adjustment.
    Scales historical prices to prevent negative values.
    """
    BASE_URL = "https://freeserv.dukascopy.com/2.0/"
    
    def __init__(self):
        self.target_columns = ["open", "high", "low", "close"]

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        print(f"[*] Fetching rollover data for {symbol}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://freeserv.dukascopy.com/2.0/?path=cfd_monthly_adjustment/index&header=false",
        }
        params = {
            "path": "cfd_monthly_adjustment/getData",
            "start": "0000000000000",
            "end": "9999999999999",
            "jsonp": "_callbacks____qmjn9av6ydd",
        }

        try:
            r = requests.get(self.BASE_URL, headers=headers, params=params, timeout=15)
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"[!] Network error: {e}")

        # Normalize JSONP
        text = r.text.strip()
        if text.startswith("_callbacks"):
            match = re.search(r"\((.*)\)", text, re.DOTALL)
            text = match.group(1) if match else "{}"

        try:
            raw_json = json.loads(text)
        except json.JSONDecodeError: return []

        if not raw_json: return []

        # Filter by symbol (Dukascopy uses '/' instead of '-')
        # e.g. "BRENT.CMD-USD-RR" -> "BRENT.CMD/USD"
        clean_sym = "/".join(symbol.replace("-RR", "").replace("-PANAMA", "").split("-")[:2])
        
        normalized = []
        for row in raw_json:
            # 1. Filter Symbol
            if str(row.get("title", "")).strip().casefold() != clean_sym.casefold():
                continue
            
            # 2. Safety Check: Skip rows with missing dates or gaps (THE FIX)
            if not row.get("date") or row.get("short") is None:
                continue

            try:
                dt = datetime.strptime(row["date"], "%d-%b-%y")
                normalized.append({"date": dt, "gap": float(row["short"])})
            except ValueError: continue

        return normalized

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        if not raw_data: return []
        if get_data is None:
            print("[!] Critical: 'api.get_data' missing.")
            return []

        # Sort Newest -> Oldest for Backward Accumulation
        raw_data.sort(key=lambda x: x["date"], reverse=True)
        
        calculated_events = []
        cum_ratio = 1.0
        
        # Clean symbol for price lookup
        src_symbol = symbol.replace("-RR", "").replace("-PANAMA", "").replace("-ADJUSTED", "")
        print(f"[*] Calculating Futures Ratios for {src_symbol}")

        for event in raw_data:
            roll_date = event["date"]
            gap = event["gap"]
            
            # Fetch 'Old Contract' Close Price on Rollover Day
            # We assume the gap happens AFTER this candle closes.
            roll_ms = int(roll_date.timestamp() * 1000)
            
            try:
                df = get_data(symbol=src_symbol, timeframe="1d", until_ms=roll_ms, limit=1, order="desc")
                
                if not df.empty and df.iloc[0]['close'] > 0:
                    old_price = float(df.iloc[0]['close'])
                    
                    # Math: New = Old + Gap
                    # Ratio = New / Old  => (Old + Gap) / Old => 1 + (Gap / Old)
                    ratio = 1.0 + (gap / old_price)
                    
                    cum_ratio *= ratio
                    calculated_events.append({"date": roll_date, "ratio": float(cum_ratio)})
                else:
                    print(f"[!] Warning: No price data for {roll_date}. Skipping ratio calc.")
            except Exception:
                pass

        # Linearize Windows (Oldest -> Newest)
        calculated_events.sort(key=lambda x: x["date"])
        
        actions = []
        prev_end = datetime(2000, 1, 1)

        for event in calculated_events:
            # Window applies to data BEFORE the rollover
            curr_end = event["date"].replace(hour=23, minute=59, second=59)

            if curr_end > prev_end:
                actions.append(TimeWindowAction(
                    id=f"roll-ratio-{event['date'].strftime('%Y%m%d')}",
                    action="*",
                    columns=list(self.target_columns),
                    value=round(event["ratio"], 8),
                    from_date=prev_end,
                    to_date=curr_end
                ))

            prev_end = curr_end + timedelta(seconds=1)

        return actions
