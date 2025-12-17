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
    Tracks trading sessions for symbols and computes the active session
    and adjusted origin times based on the server timezone and DST changes.
    """

    def __init__(self, config):
        """
        Initialize the ResampleTracker with a symbol configuration.
        """
        self.config = config
        self.last_date = None
        self.daily_session_ranges = []

    def get_active_session(self, line: str) -> str:
        """
        Determines the active session for a given timestamp line.
        """
        date_str = line[:10]

        # Recalculate session ranges only if the date has changed
        if date_str != self.last_date:
            dt_obj = datetime.fromisoformat(line[:19])
            self.daily_session_ranges = self._get_sessions_for_date(dt_obj.date(), self.config)
            
            # Precompute start and end times in minutes for faster comparison
            for s in self.daily_session_ranges:
                s['start_m'] = s["start"].hour * 60 + s["start"].minute
                s['end_m'] = s["end"].hour * 60 + s["end"].minute
            
            self.last_date = date_str

        # Compute minutes of current timestamp
        curr_h = int(line[11:13])
        curr_m = int(line[14:16])
        current_mins = curr_h * 60 + curr_m

        # Check which session the current timestamp falls into
        for s in self.daily_session_ranges:
            s_min = s['start_m']
            e_min = s['end_m']
            
            if s_min <= e_min:
                if s_min <= current_mins <= e_min:
                    return s["name"]
            else:
                # if e_min < s_min then 
                # Handle overnight sessions
                if current_mins >= s_min or current_mins <= e_min:
                    return s["name"]

        # tricky issue. related to Chicage time. The monthly candle of 2020-11-01 falls into a sunday, hence year has issue
        # quick fix: return out_of_market as session name
        return "out_of_market"
        


    def get_active_origin(self, line: str, ident: str, session_name: str, config: 'ResampleSymbol') -> str:
        """
        Computes the adjusted origin time for a specific symbol, session, and timeframe.
        """
        timestamp = datetime.fromisoformat(line[:19])
        session_cfg = config.sessions.get(session_name)
        timeframe = session_cfg.timeframes.get(ident)
        base_origin_str = timeframe.origin

        if base_origin_str == "epoch":
            return "epoch"

        # Reference date in UTC for calculating seasonal shifts
        ref_date = datetime(2025, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC"))
        tz_sydney = zoneinfo.ZoneInfo(config.timezone)
        tz_server_ref = self._get_mt4_server_tz(ref_date)

        # Gap between Sydney and server at reference date
        ref_gap = (datetime.now(tz_sydney).utcoffset().total_seconds() - 
                   datetime.now(tz_server_ref).utcoffset().total_seconds()) / 3600

        # Gap between Sydney and server at current date
        tz_server_cur = self._get_mt4_server_tz(timestamp)
        cur_gap = (timestamp.astimezone(tz_sydney).utcoffset().total_seconds() - 
                   timestamp.astimezone(tz_server_cur).utcoffset().total_seconds()) / 3600

        # Compute shift in hours
        shift = int(ref_gap - cur_gap)

        # Apply shift to base origin
        base_h, base_m = map(int, base_origin_str.split(':'))
        adjusted_h = (base_h + shift) % 24
        
        return f"{adjusted_h:02d}:{base_m:02d}"

    def is_default_session(self, config: ResampleSymbol) -> bool:
        """
        Checks if the symbol configuration uses a single default 24-hour session.
        """
        if len(config.sessions) == 1:
            if config.sessions.get("default"):
                return True
        return False

    def print(self):
        print(yaml.safe_dump(self.daily_session_ranges))

    def _get_sessions_for_date(self, current_date, config):
        """
        Returns all session start and end datetimes in server time for a given date.
        """
        tz_local = zoneinfo.ZoneInfo(config.timezone)
        tz_server = self._get_mt4_server_tz(current_date)
        sessions_for_day = []

        # Convert local session ranges to server time
        for session_name, session_item in config.sessions.items():
            for range_name, range_item in session_item.ranges.items():
                start_local = datetime.combine(current_date, 
                                              datetime.strptime(range_item.from_time, "%H:%M").time(), 
                                              tzinfo=tz_local)
                end_local = datetime.combine(current_date, 
                                            datetime.strptime(range_item.to_time, "%H:%M").time(), 
                                            tzinfo=tz_local)

                # Handle overnight sessions
                if end_local <= start_local:
                    end_local += timedelta(days=1)

                start_server = start_local.astimezone(tz_server)
                end_server = end_local.astimezone(tz_server)

                sessions_for_day.append({
                    "name": session_name,
                    "range": range_name,
                    "start": start_server.replace(tzinfo=None),
                    "end": end_server.replace(tzinfo=None)
                })

        return sessions_for_day

    def _get_mt4_server_tz(self, dt: date) -> zoneinfo.ZoneInfo:
        """
        Returns MT4 server timezone based on DST for New York.
        """
        nyc_tz = zoneinfo.ZoneInfo("America/New_York")
        nyc_dt = datetime.combine(dt, time(17, 0)).replace(tzinfo=nyc_tz)
        offset = 3 if nyc_dt.dst() != timedelta(0) else 2
        return zoneinfo.ZoneInfo(f"Etc/GMT-{offset}")


def resample_resolve_paths(symbol: str, ident: str, data_path: Path, config: ResampleConfig) -> Tuple[Optional[Path], Path, Path, bool]:
    """
    Resolve input, output, and index file paths for a resample timeframe.
    """
    timeframe: ResampleTimeframe = config.timeframes.get(ident)

    # Root timeframe: read directly from source
    if not timeframe.rule:
        root_source = Path(f"{timeframe.source}/{symbol}.csv")
        if not root_source.exists():
            raise IOError(f"Root source missing for {ident}: {root_source}")
        return None, root_source, Path(), True

    # Identify source timeframe
    source_tf = config.timeframes.get(timeframe.source)
    if not source_tf:
        raise ValueError(f"Timeframe {ident} references unknown source: {timeframe.source}")

    # Determine input path based on whether source is resampled
    if source_tf.rule is not None:
        input_path = Path(data_path) / timeframe.source / f"{symbol}.csv"
    else:
        input_path = Path(source_tf.source) / f"{symbol}.csv"

    # Set output and index paths
    output_path = Path(data_path) / ident / f"{symbol}.csv"
    index_path = Path(data_path) / ident / "index" / f"{symbol}.idx"

    # Validate input path existence
    if not input_path.exists():
        if VERBOSE:
            tqdm.write(f"  No base {ident} data for {symbol} → skipping cascading timeframes")
        raise ValueError(f"  No base {ident} data for {symbol} → skipping cascading timeframes")

    # Ensure output directory exists and create empty file if missing
    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w"):
            pass

    return input_path, output_path, index_path, False
