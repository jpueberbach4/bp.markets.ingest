#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        apple.py
Author:      JP Ueberbach
Created:     2026-02-14

Purpose:
    Provides strategies to fetch Apple's dividend and stock split history 
    from the official investor page and generate back-adjusted total return 
    windows (TimeWindowAction objects).

    This module demonstrates that corporate actions (dividends and splits) 
    are just public data combined with simple arithmetic—no vendor license 
    or proprietary feed is needed.

Design:
    - Scrapes the official Apple dividend-history table using BeautifulSoup.
    - Supports:
        * "Regular Cash" dividends (subtractive adjustments)
        * Stock splits (multiplicative adjustments)
    - Generates cumulative adjustment windows:
        * Standard Panama style (Stitched)
        * RR-style linearized total return ratios
    - Fully compatible with existing TimeWindowAction interfaces and 
      build-sidetracking-config.sh workflow.

Complexity Notes:
    - fetch_data: O(N) where N = number of table rows
    - generate_config (Panama style): O(N log N) due to sorting + O(N) processing
    - generate_config (RR style): O(N log N) due to sorting + O(N) processing
    - All core operations use only simple arithmetic; network and HTML parsing 
      are the main external costs.

Dependencies:
    - requests, BeautifulSoup4 for HTTP + HTML parsing
    - datetime, timedelta for date calculations
    - re for parsing split ratios
    - util.api.get_data for historical price lookups (RR strategy)
    - generators.sidetracking.base.IAdjustmentStrategy & TimeWindowAction

Usage:
    strategy = AppleCorporateActionsStrategy()
    events = strategy.fetch_data("AAPL")
    config = strategy.generate_config("AAPL", events)
===============================================================================
"""

from generators.sidetracking.base import IAdjustmentStrategy, TimeWindowAction
from typing import List, Dict, Any
from datetime import datetime
import requests
from datetime import timedelta,datetime
from bs4 import BeautifulSoup
from util.api import get_data
import re

# ----- NORMAL PANAMA STRATEGY - SIMPLIFIED - NEGATIVE PRICES -----

class AppleCorporateActionsStrategy(IAdjustmentStrategy):
    """Simplified Strategy for Apple Standard Panama (Stitched) adjustments."""

    def __init__(self):
        self.url = "https://investor.apple.com/dividend-history/default.aspx"
        self.target_columns = ["open", "high", "low", "close"]

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        print(f"[*] Fetching corporate actions for {symbol}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            r = requests.get(self.url, headers=headers, timeout=15)
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"[!] Fetch failed: {e}")

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table: return []

        events = []
        for row in table.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 5: continue

            # Quick helper to clean text and fix typos
            get_col = lambda i: cols[i].get_text(strip=True).replace(" ,", ",").replace("*", "")
            
            typ = get_col(4)
            is_split = "Stock Split" in typ
            
            # Select Date: Payable (col 2) for Splits, Record (col 1) for Divs
            date_str = get_col(2) if is_split else get_col(1)

            try:
                dt = datetime.strptime(date_str, "%B %d, %Y")
            except ValueError: continue

            event = {"date": dt, "type": typ}

            if "Regular Cash" in typ:
                try:
                    event["dividend"] = float(get_col(3).replace("$", ""))
                    events.append(event)
                except ValueError: continue
            
            elif is_split:
                match = re.search(r"(\d+)\s*-?for-?\s*(\d+)", typ)
                if match:
                    event["split_factor"] = int(match.group(1)) / int(match.group(2))
                    events.append(event)
                    
        return events

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        if not raw_data: return []

        # Pass 1: Calculate Cumulative State (Newest -> Oldest)
        raw_data.sort(key=lambda x: x["date"], reverse=True)
        
        segments = []
        cum_split = 1.0
        cum_div = 0.0

        for event in raw_data:
            is_split = "split_factor" in event
            
            if is_split:
                cum_split *= (1.0 / float(event["split_factor"]))
            else:
                cum_div += (event["dividend"] * cum_split)

            segments.append({
                "date": event["date"],
                "is_split": is_split,
                "split_val": float(cum_split),
                "div_val": float(cum_div)
            })

        # Pass 2: Stitch Windows (Oldest -> Newest)
        segments.sort(key=lambda x: x["date"])
        
        actions = []
        prev_end = datetime(2000, 1, 1)

        for seg in segments:
            # Window Logic: Splits include the event day; Divs end the day before
            cutoff_date = seg["date"] if seg["is_split"] else seg["date"] - timedelta(days=1)
            curr_end = cutoff_date.replace(hour=23, minute=59, second=59)

            if curr_end > prev_end:
                date_str = seg["date"].strftime('%Y%m%d')
                
                # Add Split Action (*)
                if abs(seg["split_val"] - 1.0) > 1e-9:
                    actions.append(TimeWindowAction(
                        id=f"seg-split-{date_str}", action="*", 
                        columns=self.target_columns, value=round(seg["split_val"], 8),
                        from_date=prev_end, to_date=curr_end
                    ))
                
                # Add Dividend Action (-)
                if abs(seg["div_val"]) > 1e-9:
                    actions.append(TimeWindowAction(
                        id=f"seg-div-{date_str}", action="-", 
                        columns=self.target_columns, value=round(seg["div_val"], 6),
                        from_date=prev_end, to_date=curr_end
                    ))

            prev_end = curr_end + timedelta(seconds=1)

        return actions

# ----- RETURN RATIO STRATEGY - SIMPLIFIED - NO NEGATIVE PRICES -----

class AppleCorporateActionsStrategyRR(IAdjustmentStrategy):
    """Simplified Strategy for Apple Total Return (Ratio-based) adjustments."""

    def __init__(self):
        self.url = "https://investor.apple.com/dividend-history/default.aspx"
        self.target_columns = ["open", "high", "low", "close"]

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        print(f"[*] Fetching corporate actions for {symbol}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            r = requests.get(self.url, headers=headers, timeout=15)
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"[!] Fetch failed: {e}")

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table: return []

        events = []
        for row in table.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 5: continue

            # Helper to clean text
            get_col = lambda i: cols[i].get_text(strip=True).replace(" ,", ",").replace("*", "")
            
            typ = get_col(4)
            is_split = "Stock Split" in typ
            
            # Select Date: Payable (col 2) for Splits, Record (col 1) for Divs
            date_str = get_col(2) if is_split else get_col(1)

            try:
                dt = datetime.strptime(date_str, "%B %d, %Y")
            except ValueError: continue

            event = {"date": dt, "type": "split" if is_split else "div"}

            if "Regular Cash" in typ:
                try:
                    event["dividend"] = float(get_col(3).replace("$", ""))
                    events.append(event)
                except ValueError: continue
            
            elif is_split:
                match = re.search(r"(\d+)\s*-?for-?\s*(\d+)", typ)
                if match:
                    event["split_factor"] = int(match.group(1)) / int(match.group(2))
                    events.append(event)
                    
        return events

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        if not raw_data: return []
        if get_data is None:
            print("[!] Critical: 'api.get_data' missing.")
            return []

        # Pass 1: Calculate Cumulative Ratios (Newest -> Oldest)
        raw_data.sort(key=lambda x: x["date"], reverse=True)
        
        calculated_events = []
        cum_ratio = 1.0
        
        # Strip suffixes to query raw price data
        src_symbol = symbol

        for event in raw_data:
            if event["type"] == "split":
                cum_ratio *= (1.0 / float(event["split_factor"]))
                calculated_events.append({**event, "ratio": float(cum_ratio)})
            
            elif event["type"] == "div":
                # Peek at price on Ex-Date (Record Date - 1 day approx)
                event_ms = int(event["date"].timestamp() * 1000)
                try:
                    df = get_data(symbol=src_symbol, timeframe="1d", until_ms=event_ms, limit=1, order="desc")
                    if not df.empty and df.iloc[0]['close'] > 0:
                        div_ratio = 1.0 - (float(event["dividend"]) / float(df.iloc[0]['close']))
                        cum_ratio *= div_ratio
                        calculated_events.append({**event, "ratio": float(cum_ratio)})
                except Exception:
                    pass # Skip if data missing

        # Pass 2: Linearize Windows (Oldest -> Newest)
        calculated_events.sort(key=lambda x: x["date"])
        
        actions = []
        prev_end = datetime(2000, 1, 1)

        for event in calculated_events:
            # Splits end ON event day; Divs end BEFORE event day
            cutoff = event["date"] if event["type"] == "split" else event["date"] - timedelta(days=1)
            curr_end = cutoff.replace(hour=23, minute=59, second=59)

            if curr_end > prev_end:
                actions.append(TimeWindowAction(
                    id=f"{event['type']}-{event['date'].strftime('%Y%m%d')}",
                    action="*",
                    columns=self.target_columns,
                    value=round(event["ratio"], 8),
                    from_date=prev_end,
                    to_date=curr_end
                ))

            prev_end = curr_end + timedelta(seconds=1)

        return actions