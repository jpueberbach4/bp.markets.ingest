#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        helper.py
 Author:      JP Ueberbach
 Created:     2025-12-16
 Description: Module for handling resample tracking, session detection, and 
              file path resolution for financial symbol data resampling.

              This module provides:
              - ResampleTracker: Track active trading sessions and compute 
                adjusted origin times.
              - resample_resolve_paths: Determine input, output, and index paths 
                for resampled data.

 Requirements:
     - Python 3.8+
     - backports.zoneinfo

 License:
     MIT License
===============================================================================
"""
import copy
import yaml
from dataclasses import asdict
from typing import Dict, Tuple, Optional
from pathlib import Path
from datetime import datetime, time, timedelta, date
from config.app_config import AppConfig, ResampleConfig, ResampleSymbol, ResampleSymbolTradingSession, ResampleTimeframe

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo


class ResampleTracker:
    """
    Tracks trading sessions and computes active sessions and adjusted origin times.

    This class handles session tracking for symbols, converting local session
    times to MT4 server times, handling overnight sessions, and adjusting
    origin times based on server timezone and Daylight Saving Time (DST) changes.
    """

    def __init__(self, config):
        """
        Initializes a ResampleTracker instance with a symbol configuration.

        This constructor sets up the configuration, prepares tracking for the last
        processed date, and initializes the daily session ranges.

        Args:
            config: The symbol configuration containing sessions, timeframes, and timezone.
        """
        # Store the symbol configuration
        self.config = config

        # Keep track of the last date processed to avoid redundant recalculations
        self.last_date = None

        # List to hold the precomputed session ranges for the current date
        self.daily_session_ranges = []


    def get_active_session(self, line: str) -> str:
        """
        Determines the active trading session for a given timestamp line.

        This method calculates which session a timestamp falls into by converting
        session start and end times to minutes for efficient comparison. Overnight
        sessions that span midnight are also handled correctly.

        Args:
            line (str): A line of data containing the timestamp (ISO format) at the start.

        Returns:
            str: The name of the active session corresponding to the timestamp.

        Raises:
            ValueError: If the timestamp does not fall into any session.
        """
        # Extract the date portion from the timestamp line
        date_str = line[:10]

        # Recalculate session ranges if the date has changed
        if date_str != self.last_date:
            dt_obj = datetime.fromisoformat(line[:19])
            self.daily_session_ranges = self._get_sessions_for_date(dt_obj.date(), self.config)

            # Precompute start and end times in minutes for faster comparisons
            for s in self.daily_session_ranges:
                s['start_m'] = s["start"].hour * 60 + s["start"].minute
                s['end_m'] = s["end"].hour * 60 + s["end"].minute

            self.last_date = date_str

        # Compute the current timestamp in minutes
        curr_h = int(line[11:13])
        curr_m = int(line[14:16])
        current_mins = curr_h * 60 + curr_m

        # Check which session the current timestamp falls into
        for s in self.daily_session_ranges:
            s_min = s['start_m']
            e_min = s['end_m']

            if s_min <= e_min:
                # Normal session within the same day
                if s_min <= current_mins <= e_min:
                    return s["name"]
            else:
                # Overnight session spanning midnight
                if current_mins >= s_min or current_mins <= e_min:
                    return s["name"]

        raise ValueError(f"Line {line} is out_of_market.")


    def get_active_origin(self, line: str, ident: str, session_name: str, config: 'ResampleSymbol') -> str:
        """
        Computes the adjusted origin time for a specific symbol, session, and timeframe.

        This method adjusts the configured base origin hour for a session and timeframe
        to account for differences between the local timezone and the MT4 server timezone,
        including seasonal DST shifts.

        Args:
            line (str): A line of data containing the timestamp (ISO format) at the start.
            ident (str): The timeframe identifier.
            session_name (str): The name of the session.
            config (ResampleSymbol): The symbol configuration containing sessions and timeframes.

        Returns:
            str: The adjusted origin time in "HH:MM" format, or "epoch" if the base origin is "epoch".
        """
        # Extract the timestamp from the input line
        timestamp = datetime.fromisoformat(line[:19])

        # Get the session and timeframe configuration
        session_cfg = config.sessions.get(session_name)
        timeframe = session_cfg.timeframes.get(ident)
        base_origin_str = timeframe.origin

        # Return early if the base origin is 'epoch'
        if base_origin_str == "epoch":
            return "epoch"

        # Reference date in UTC to calculate seasonal shifts
        ref_date = datetime(2025, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC"))
        tz_sydney = zoneinfo.ZoneInfo(config.timezone)
        tz_server_ref = self._get_mt4_server_tz(ref_date)

        # Calculate the timezone gap between Sydney and server at reference date
        ref_gap = (datetime.now(tz_sydney).utcoffset().total_seconds() - 
                datetime.now(tz_server_ref).utcoffset().total_seconds()) / 3600

        # Calculate the timezone gap between Sydney and server at current timestamp
        tz_server_cur = self._get_mt4_server_tz(timestamp)
        cur_gap = (timestamp.astimezone(tz_sydney).utcoffset().total_seconds() - 
                timestamp.astimezone(tz_server_cur).utcoffset().total_seconds()) / 3600

        # Compute the shift in hours
        shift = int(ref_gap - cur_gap)

        # Apply the shift to the base origin hour
        base_h, base_m = map(int, base_origin_str.split(':'))
        adjusted_h = (base_h + shift) % 24

        return f"{adjusted_h:02d}:{base_m:02d}"


    def is_default_session(self, config: ResampleSymbol) -> bool:
        """
        Determines if the symbol configuration uses a single default 24-hour session.

        Args:
            config (ResampleSymbol): The symbol configuration containing session definitions.

        Returns:
            bool: True if the configuration has exactly one session named "default", otherwise False.
        """
        # Check if there is only one session defined
        if len(config.sessions) == 1:
            # Check if the single session is named "default"
            if config.sessions.get("default"):
                return True
        return False


    def _get_sessions_for_date(self, current_date, config):
        """
        Returns all trading session start and end datetimes in MT4 server time for a given date.

        This method converts configured local session times into server time, handling
        overnight sessions that span midnight.

        Args:
            current_date (date): The date for which to retrieve trading sessions.
            config: Configuration object containing session definitions and timezone.

        Returns:
            List[Dict]: A list of dictionaries, each containing:
                - "name": Session name
                - "range": Range name within the session
                - "start": Session start datetime in server time (timezone-naive)
                - "end": Session end datetime in server time (timezone-naive)
        """
        # Local timezone from the configuration
        tz_local = zoneinfo.ZoneInfo(config.timezone)

        # MT4 server timezone for the given date
        tz_server = self._get_mt4_server_tz(current_date)

        sessions_for_day = []

        # Iterate over all sessions defined in the configuration
        for session_name, session_item in config.sessions.items():
            for range_name, range_item in session_item.ranges.items():
                # Convert local session start and end times to datetime
                start_local = datetime.combine(
                    current_date,
                    datetime.strptime(range_item.from_time, "%H:%M").time(),
                    tzinfo=tz_local,
                )
                end_local = datetime.combine(
                    current_date,
                    datetime.strptime(range_item.to_time, "%H:%M").time(),
                    tzinfo=tz_local,
                )

                # Adjust for overnight sessions that span midnight
                if end_local <= start_local:
                    end_local += timedelta(days=1)

                # Convert local times to server timezone
                start_server = start_local.astimezone(tz_server)
                end_server = end_local.astimezone(tz_server)

                # Append the session with timezone-naive server times
                sessions_for_day.append({
                    "name": session_name,
                    "range": range_name,
                    "start": start_server.replace(tzinfo=None),
                    "end": end_server.replace(tzinfo=None),
                })

        return sessions_for_day


    def _get_mt4_server_tz(self, dt: date) -> zoneinfo.ZoneInfo:
        """
        Determines the MT4 server timezone for a given date.

        The MT4 server timezone is derived from New York time. The GMT offset
        changes depending on whether Daylight Saving Time (DST) is in effect
        in New York at the 17:00 local rollover time.

        Args:
            dt: The date for which to determine the MT4 server timezone.

        Returns:
            A ZoneInfo instance representing the MT4 server timezone
            (Etc/GMT-3 during DST, Etc/GMT-2 otherwise).
        """
        # Use New York timezone as the reference for determining DST state
        nyc_tz = zoneinfo.ZoneInfo("America/New_York")

        # Evaluate DST at 17:00 New York time, which corresponds to the MT4 rollover
        nyc_dt = datetime.combine(dt, time(17, 0)).replace(tzinfo=nyc_tz)

        # Select the MT4 GMT offset based on whether DST is active in New York
        offset = 3 if nyc_dt.dst() != timedelta(0) else 2

        # Return the fixed GMT timezone used by the MT4 server
        return zoneinfo.ZoneInfo(f"Etc/GMT-{offset}")


