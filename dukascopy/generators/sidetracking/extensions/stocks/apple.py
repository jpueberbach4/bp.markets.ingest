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


class AppleCorporateActionsStrategy(IAdjustmentStrategy):
    """Strategy to calculate Apple's standard total return adjustments (Stitched Panama style)."""

    def __init__(self):
        """Initialize the strategy with Apple IR URL and target OHLC columns.

        Complexity:
            O(1) — constant time to set initial properties.
        """
        # URL for Apple's dividend & split history
        self.url = "https://investor.apple.com/dividend-history/default.aspx"
        # Columns that will be adjusted in TR calculation
        self.target_columns = ["open", "high", "low", "close"]

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch and parse Apple's dividend and stock split history.

        Args:
            symbol (str): Stock symbol (ignored, Apple fixed URL used).

        Returns:
            List[Dict[str, Any]]: List of events with 'date', 'type', and optionally
                                  'dividend' or 'split_factor'.

        Complexity:
            O(N) — N is the number of rows in the dividend/split table.
        """
        # Inform the user
        print(f"[*] Fetching corporate actions for {symbol} from Apple IR...")

        # Headers to mimic a real browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

        # Try to fetch Apple IR page
        try:
            session = requests.Session()  # O(1)
            r = session.get(self.url, headers=headers, timeout=15)  # network call, O(1)
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"[!] Failed to fetch Apple dividend page: {e}")

        # Parse the HTML
        soup = BeautifulSoup(r.text, "html.parser")  # O(N) in HTML size
        table = soup.find("table")  # O(N) in HTML size
        if not table:
            raise Exception("[!] Failed to fetch Apple dividend page (DATA MISSING)") 

        events = []
        # Loop over each row in table body
        for row in table.select("tbody tr"):  # O(R) for R rows
            cols = row.find_all("td")  # O(C), C columns per row
            if len(cols) < 5: 
                continue

            # Extract record & payable dates
            record_date_str = cols[1].get_text(strip=True).replace(" ,", ",").replace("*", "")
            payable_date_str = cols[2].get_text(strip=True).replace(" ,", ",").replace("*", "")

            # Amount (dividend) and type (dividend/split)
            amount_str = cols[3].get_text(strip=True)
            typ = cols[4].get_text(strip=True)

            # Conditional date selection
            target_date_str = payable_date_str if "Stock Split" in typ else record_date_str

            # Convert string to datetime
            try:
                dt = datetime.strptime(target_date_str, "%B %d, %Y")  # O(1)
            except ValueError:
                continue

            event = {"date": dt, "type": typ}

            # Handle regular cash dividends
            if "Regular Cash" in typ:
                try:
                    event["dividend"] = float(amount_str.replace("$", "").strip())
                    events.append(event)
                except ValueError: 
                    continue

            # Handle stock splits
            elif "Stock Split" in typ:
                match = re.search(r"(\d+)\s*-?for-?\s*(\d+)", typ)  # O(1) regex on small string
                if match:
                    event["split_factor"] = int(match.group(1)) / int(match.group(2))
                    events.append(event)

        return events  # O(R)

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        """Generate stitched Standard Panama total return config.

        Args:
            symbol (str): Stock symbol.
            raw_data (List[Dict[str, Any]]): List of raw dividend/split events.

        Returns:
            List[TimeWindowAction]: List of TimeWindowAction objects representing TR-adjusted windows.

        Complexity:
            O(N log N) — due to sorting + O(N) processing, where N = len(raw_data).
        """
        if not raw_data:  # O(1)
            return []

        # --- PASS 1: Compute cumulative state (Newest -> Oldest) ---
        raw_data.sort(key=lambda x: x["date"], reverse=True)  # O(N log N)
        
        history_segments = []
        cum_split_factor = 1.0  # running multiplicative split factor
        cum_dividend_offset = 0.0  # running dividend offset

        # Calculate cumulative state for each event
        for event in raw_data:  # O(N)
            current_date = event["date"]

            if "dividend" in event:  # O(1)
                # Add dividend adjusted for splits so far
                cum_dividend_offset += (event["dividend"] * cum_split_factor)

            elif "split_factor" in event:  # O(1)
                # Apply split multiplier
                cum_split_factor *= (1.0 / float(event["split_factor"]))

            # Save the state for this event
            history_segments.append({
                "date": current_date,
                "type": "Stock Split" if "split_factor" in event else "Dividend",
                "split_val": float(cum_split_factor),
                "div_val": float(cum_dividend_offset)
            })

        # --- PASS 2: Stitch windows (Oldest -> Newest) ---
        history_segments.sort(key=lambda x: x["date"])  # O(N log N)
        
        actions = []
        prev_window_end = datetime(2000, 1, 1, 0, 0, 0)  # start of timeline

        for segment in history_segments:  # O(N)
            seg_date = segment["date"]

            # Window ends the second before record/ex-date
            current_window_end = (seg_date - timedelta(days=1)).replace(hour=23, minute=59, second=59) \
                if segment["type"] == "Dividend" else seg_date.replace(hour=23, minute=59, second=59)

            if current_window_end > prev_window_end:
                # 1. Split action (multiplicative)
                if abs(segment["split_val"] - 1.0) > 1e-9:
                    actions.append(TimeWindowAction(
                        id=f"seg-split-{seg_date.strftime('%Y%m%d')}",
                        action="*",
                        columns=list(self.target_columns),
                        value=round(segment["split_val"], 8),
                        from_date=prev_window_end,
                        to_date=current_window_end
                    ))

                # 2. Dividend action (subtractive)
                if abs(segment["div_val"]) > 1e-9:
                    actions.append(TimeWindowAction(
                        id=f"seg-div-{seg_date.strftime('%Y%m%d')}",
                        action="-",
                        columns=list(self.target_columns),
                        value=round(segment["div_val"], 6),
                        from_date=prev_window_end,
                        to_date=current_window_end
                    ))

            # Stitch next window start 1 second later
            prev_window_end = current_window_end + timedelta(seconds=1)

        return actions  # O(N)

class AppleCorporateActionsStrategyRR(IAdjustmentStrategy):
    """Strategy to calculate Apple's total return adjustments from dividends and stock splits."""

    def __init__(self):
        """Initialize the strategy with Apple IR URL and target OHLC columns.

        Complexity:
            O(1) — constant time to set initial properties.
        """
        # URL to fetch Apple dividend & split history
        self.url = "https://investor.apple.com/dividend-history/default.aspx"
        # Columns that will be adjusted in total return calculations
        self.target_columns = ["open", "high", "low", "close"]

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch and parse Apple's dividend and stock split history.

        Args:
            symbol (str): Stock symbol (ignored, Apple fixed URL is used).

        Returns:
            List[Dict[str, Any]]: List of events with keys 'date', 'type', 
                                  and optionally 'dividend' or 'split_factor'.

        Complexity:
            O(N) — N is the number of rows in the dividend/split table.
        """
        # Inform the user that fetch started
        print(f"[*] Fetching corporate actions for {symbol} from Apple IR...")

        # HTTP headers to mimic a real browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

        # Attempt to get the Apple IR page
        try:
            session = requests.Session()  # O(1)
            r = session.get(self.url, headers=headers, timeout=15)  # network call, O(1)
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"[!] Failed to fetch Apple dividend page: {e}")

        # Parse the HTML using BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")  # O(N) in document size
        table = soup.find("table")  # O(N) in document size

        if not table:
            raise Exception("[!] Failed to fetch Apple dividend page (DATA MISSING)") 

        events = []

        # Loop through each row in the table body
        for row in table.select("tbody tr"):  # O(R) where R = number of rows
            cols = row.find_all("td")  # O(C) where C = number of columns per row
            if len(cols) < 5:
                continue  # skip invalid rows

            # Extract record date and payable date as strings, clean formatting
            record_date_str = cols[1].get_text(strip=True).replace(" ,", ",").replace("*", "")
            payable_date_str = cols[2].get_text(strip=True).replace(" ,", ",").replace("*", "")

            # Amount (dividend) and type (dividend/stock split)
            amount_str = cols[3].get_text(strip=True)
            typ = cols[4].get_text(strip=True)

            # Choose target date: payable date for split, record date for dividend
            target_date_str = payable_date_str if "Stock Split" in typ else record_date_str

            # Convert string to datetime object
            try:
                dt = datetime.strptime(target_date_str, "%B %d, %Y")  # O(1)
            except ValueError:
                continue  # skip invalid dates

            # Initialize event dict
            event = {"date": dt, "type": typ}

            # Handle regular cash dividends
            if "Regular Cash" in typ:
                try:
                    event["dividend"] = float(amount_str.replace("$", "").strip())  # O(1)
                    events.append(event)
                except ValueError:
                    continue

            # Handle stock splits
            elif "Stock Split" in typ:
                match = re.search(r"(\d+)\s*-?for-?\s*(\d+)", typ)  # O(1), regex on short string
                if match:
                    event["split_factor"] = int(match.group(1)) / int(match.group(2))  # O(1)
                    events.append(event)

        return events  # O(R)

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        """Generate linearized total return configuration from raw dividend/split events.

        Args:
            symbol (str): Stock symbol.
            raw_data (List[Dict[str, Any]]): Raw events from fetch_data.

        Returns:
            List[TimeWindowAction]: List of TimeWindowAction objects representing TR-adjusted windows.

        Complexity:
            O(N log N) — sorting events + O(N) processing, where N = len(raw_data).
        """
        if not raw_data:  # O(1)
            return []

        if get_data is None:  # O(1)
            print("[!] Critical: 'api.get_data' not found. Cannot calculate Total Return Ratios.")
            return []

        # Sort raw events by date descending (newest first)
        raw_data.sort(key=lambda x: x["date"], reverse=True)  # O(N log N)

        calculated_events = []  # will store cumulative ratios
        cumulative_ratio = 1.0

        # Clean symbol for API lookup
        source_symbol = symbol
        print(f"[*] Calculating Total Return Ratios using raw data from: {source_symbol}")

        # Loop over each event (dividend or split)
        for event in raw_data:  # O(N)
            current_date = event["date"]

            if "split_factor" in event:  # O(1)
                cumulative_ratio *= (1.0 / float(event["split_factor"]))  # adjust cumulative ratio
                calculated_events.append({
                    "date": current_date,
                    "ratio": float(cumulative_ratio),
                    "type": "split"
                })

            elif "dividend" in event:  # O(1)
                # Fetch previous day's closing price (API call, O(1) per call)
                event_ms = int(current_date.timestamp() * 1000)
                try:
                    price_df = get_data(
                        symbol=source_symbol,
                        timeframe="1d",
                        until_ms=event_ms,
                        limit=1,
                        order="desc"
                    )
                except Exception as e:
                    print(f"[!] Data error {current_date}: {e}")
                    price_df = None

                if price_df is not None and not price_df.empty:
                    try:
                        close_px = float(price_df.iloc[0]['close'])  # O(1)
                        if close_px > 0:
                            div_ratio = 1.0 - (float(event["dividend"]) / close_px)
                            cumulative_ratio *= div_ratio
                            calculated_events.append({
                                "date": current_date,
                                "ratio": float(cumulative_ratio),
                                "type": "div"
                            })
                    except (KeyError, IndexError):
                        pass
                else:
                    print(f"[!] Warning: No price data for {current_date}. Skipping dividend.")

        # Sort calculated events by ascending date (oldest first)
        calculated_events.sort(key=lambda x: x["date"])  # O(N log N)

        actions = []  # will store TimeWindowAction objects
        prev_window_end = datetime(2000, 1, 1, 0, 0, 0)  # starting baseline

        # Create linearized time windows
        for event in calculated_events:  # O(N)
            event_date = event["date"]

            # Set window end: for split use same day 23:59:59, for dividend day before
            current_window_end = (event_date.replace(hour=23, minute=59, second=59)
                                  if event["type"] == "split"
                                  else (event_date - timedelta(days=1)).replace(hour=23, minute=59, second=59))

            if current_window_end > prev_window_end:  # O(1)
                actions.append(TimeWindowAction(
                    id=f"{event['type']}-{event_date.strftime('%Y%m%d')}",  # O(1)
                    action="*",  # adjust all columns
                    columns=list(self.target_columns),  # O(C), small C=4
                    value=round(event["ratio"], 8),  # O(1)
                    from_date=prev_window_end,
                    to_date=current_window_end
                ))

            # Next window starts 1 second after previous ends
            prev_window_end = current_window_end + timedelta(seconds=1)

        return actions  # O(N)
