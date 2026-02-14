#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        apple.py
Author:      JP Ueberbach (adapted by Grok)
Created:     2026-02-14

This is an AI-generated example. No time. Need to go in 30 mins.

Purpose:
    Fetches dividend + stock split history from Apple's investor page and
    generates proper back-adjustment windows (subtract dividends, apply split
    ratios) using the same TimeWindowAction interface as Panama.

    This proves the same point: corporate actions are just public data + simple
    arithmetic — no magic, no vendor needed.

Design:
    - Scrapes the official dividend-history table
    - Handles both "Regular Cash" dividends (subtract) and stock splits (* or /)
    - Generates cumulative adjustment windows (oldest data gets full adjustment)
    - Fully compatible with the existing build-sidetracking-config.sh
===============================================================================
"""

from generators.sidetracking.base import IAdjustmentStrategy, TimeWindowAction
from typing import List, Dict, Any
from datetime import datetime
import requests
from datetime import timedelta,datetime
from bs4 import BeautifulSoup
import re


class AppleCorporateActionsStrategy(IAdjustmentStrategy):

    def __init__(self):
        self.url = "https://investor.apple.com/dividend-history/default.aspx"
        self.target_columns = ["open", "high", "low", "close"]
        # Volume is usually NOT adjusted for dividends (only for contract size changes)

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch and parse Apple's dividend + split history table."""
        print(f"[*] Fetching corporate actions for {symbol} from Apple IR... (VERY EXPERIMENTAL AND DONE IN A HURRY. DEMONSTRATION PURPOSES ONLY)")

        # Modern browser headers to bypass 403 Forbidden
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.google.com/",
        }

        try:
            # Using a session is better for maintaining connection state
            session = requests.Session()
            r = session.get(self.url, headers=headers, timeout=15)
            r.raise_for_status()
        except Exception as e:
            # If 403 persists, the IP might be temporarily flagged
            raise Exception(f"[!] Failed to fetch Apple dividend page: {e}")

        soup = BeautifulSoup(r.text, "html.parser")
        
        # Apple's table usually has a specific ID or class. 
        # Using a broader search if the specific class changed.
        table = soup.find("table") 
        
        if not table:
            print("[!] Warning: Could not find data table on page.")
            return []

        # Parse logic fix for asterisks and splits
        events = []
        for row in table.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 5: continue

            payable = cols[2].get_text(strip=True).replace("*", "") # Clean asterisk
            amount  = cols[3].get_text(strip=True)
            typ     = cols[4].get_text(strip=True)

            try:
                dt = datetime.strptime(payable, "%B %d, %Y")
            except ValueError: continue

            event = {"date": dt, "type": typ}

            if "Regular Cash" in typ:
                event["dividend"] = float(amount.replace("$", "").strip())
                events.append(event)
            elif "Stock Split" in typ:
                # regex handles "4-for-1" or "4 - for - 1"
                match = re.search(r"(\d+)\s*-?for-?\s*(\d+)", typ)
                if match:
                    event["split_factor"] = int(match.group(1)) / int(match.group(2))
                    events.append(event)
        return events

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        if not raw_data: return []

        # Sort Newest to Oldest for Panama calculation
        # (We calculate adjustment needed for PAST data relative to TODAY)
        raw_data.sort(key=lambda x: x["date"], reverse=True)

        actions = []
        cum_split_factor = 1.0
        cum_dividend_offset = 0.0

        # We start at "today" and go backwards
        # The newest contract has 0 adjustment.
        # As we cross a split/div going backwards, we increase the adjustment for all data OLDER than that.
        
        for i, event in enumerate(raw_data):
            # Window for data BEFORE this event
            # from_date: some far past or the next event
            # to_date: The day before this event at 23:59:59
            current_date = event["date"]
            window_end = (current_date - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            
            # The Panama Method for Dividends is additive (Price + Offset)
            # The Ratio Method for Splits is multiplicative (Price * Factor)
            
            if "dividend" in event:
                # Every share held before this date was worth more by the dividend amount
                # but because we work with a unified cumulative offset:
                # We must adjust the dividend amount by the cumulative split factor 
                # that has occurred SINCE then to keep it relative to "today's" price.
                cum_dividend_offset += (event["dividend"] * cum_split_factor)
                
                actions.append(TimeWindowAction(
                    id=f"div-{current_date.strftime('%Y%m%d')}",
                    action="-",
                    columns=list(self.target_columns),
                    value=round(cum_dividend_offset, 6),
                    from_date=datetime(2000, 1, 1), # Far past
                    to_date=window_end
                ))

            elif "split_factor" in event:
                # Prices before a 4-for-1 split were 4x higher.
                # So we multiply historical data by (1 / 4) to bring it to today's level.
                # Note: cum_split_factor accumulates all splits from "now" to "then"
                cum_split_factor *= (1 / event["split_factor"])
                
                actions.append(TimeWindowAction(
                    id=f"split-{current_date.strftime('%Y%m%d')}",
                    action="*",
                    columns=list(self.target_columns),
                    value=round(cum_split_factor, 6),
                    from_date=datetime(2000, 1, 1),
                    to_date=window_end
                ))

        # Sort actions by date ascending for the YAML output
        actions.sort(key=lambda x: x.to_date)
        return actions