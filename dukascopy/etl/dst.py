#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        dst.py
 Author:      JP Ueberbach
 Created:     2025-12-14
 Description: Utilities for resolving time shifts for financial symbols based 
              on timezone and daylight saving time (DST) rules.

              This module determines the correct time shift (in milliseconds) 
              for a given symbol and date by:
             
              - Resolving the symbol's associated timezone
              - Computing the UTC offset for that date
              - Mapping the UTC offset to a configured time shift

              If no specific mapping is found, a global default time shift is used.

 Usage:
     python3 resample.py

 Requirements:
     - Python 3.8+

 License:
     MIT License
===============================================================================
"""
import pytz
from datetime import date, datetime
from config.app_config import TransformConfig

# Cache placeholder for potential future optimization of timezone offset lookups
TIMEZONE_SHIFT_CACHE = {}


def get_utc_offset_minutes(dt: date, timezone: str) -> int:
    """
    Compute the UTC offset, in minutes, for a given date and timezone.

    The offset is evaluated at 12:00 (noon) local time to avoid edge cases
    around daylight saving time transitions, which typically occur near
    midnight or early morning.

    Args:
        dt: The date for which to compute the UTC offset.
        timezone: A valid IANA timezone string (e.g., "Europe/Berlin").

    Returns:
        The UTC offset in minutes (e.g., +120, -300).
    """
    # Resolve the timezone object
    tz = pytz.timezone(timezone)

    # Use noon to safely avoid DST transition boundaries
    dt_check = datetime(dt.year, dt.month, dt.day, 12, 0, 0)

    # Localize the naive datetime to the target timezone
    tz_aware_dt = tz.localize(dt_check)

    # Extract the UTC offset as a timedelta
    utc_offset_timedelta = tz_aware_dt.utcoffset()

    # Convert the offset from seconds to minutes
    utc_offset_minutes = int(utc_offset_timedelta.total_seconds() / 60)

    return utc_offset_minutes


def get_symbol_time_shift_ms(dt: date, symbol: str, config: TransformConfig) -> int:
    """
    Determine the time shift (in milliseconds) for a symbol on a given date.

    The function:
    - Finds the timezone configuration that contains the symbol
    - Computes the UTC offset for the given date
    - Maps the offset to a configured time shift
    - Falls back to a global default if the symbol or offset is not found

    Args:
        dt: The date for which the time shift should be calculated.
        symbol: The symbol whose time shift is being resolved.
        config: Transformation configuration containing timezone mappings,
                symbol groups, and offset-to-shift mappings.

    Returns:
        The resolved time shift in milliseconds.
    """
    # Iterate through configured timezones
    for name, timezone in config.timezones.items():
        # Check whether the symbol or the wildcard '*' belongs to this timezone group
        if symbol in timezone.symbols or '*' in timezone.symbols:
            try:
                # Compute the UTC offset for the given date
                offset_in_minutes = get_utc_offset_minutes(dt, name)
            except ValueError as e:
                # Invalid timezone name or localization failure
                print(f"Error checking DST for {symbol} on {dt}: {e}")
                return config.time_shift_ms

            # Return the mapped shift if the offset is explicitly configured
            if offset_in_minutes in timezone.offset_to_shift_map:
                return timezone.offset_to_shift_map[offset_in_minutes]
            else:
                # Handle unexpected or newly introduced DST offsets
                print(
                    f"Warning: Symbol {symbol} on {dt} has unmapped UTC offset "
                    f"{offset_in_minutes} for TZ {name}. Falling back to global shift."
                )
                return config.time_shift_ms

    # Symbol not found in any timezone group; use the global default
    return config.time_shift_ms
