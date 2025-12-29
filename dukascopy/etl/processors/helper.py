#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        helper.py
 Author:      JP Ueberbach
 Created:     2025-12-29
 Description: Helper utilities
              Mainly for date conversion

 Usage:
     Imported and invoked by the resampling processors.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy

 License:
     MIT License
===============================================================================
"""

import pytz
import pandas as pd
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

def convert_to_server_time_str(dt: str, origin_tz: str, dst_tz: str) -> str:
    """Converts a naive datetime string from an origin timezone to server time.

    The conversion determines the server timezone based on whether Daylight
    Saving Time (DST) is active in the given DST reference timezone. If DST is
    active, the server timezone is assumed to be `Etc/GMT-3`; otherwise,
    `Etc/GMT-2`.

    Args:
        dt (str): Naive datetime string (e.g. "2024-06-17 00:00:00") assumed to
            be in the `origin_tz` timezone.
        origin_tz (str): Timezone name representing the original timezone
            of `dt` (e.g. "UTC", "Europe/London").
        dst_tz (str): Timezone name used to determine DST state
            (e.g. "America/New_York").

    Returns:
        str: Datetime string converted to server time, formatted as
        "%Y-%m-%d %H:%M:%S".

    Notes:
        - The input datetime is treated as naive and explicitly localized to
          `origin_tz`.
        - DST determination is based solely on `dst_tz`, not `origin_tz`.
        - The returned value is a string and may be converted back to a
          datetime by the caller if needed.
    """
    # Setup the timezone objects needed for conversion
    tz_dst = pytz.timezone(dst_tz)
    tz_origin = pytz.timezone(origin_tz)

    # The dt is naive, convert to datetime (without a timezone)
    naive_ts = pd.Timestamp(dt).to_pydatetime().replace(tzinfo=None)

    # Now make sure timestamp is assigned the origin_tz timezone
    ts_origin = tz_origin.localize(naive_ts)

    # Determine dst state based on tz_dst and origin_ts
    dst_zone = ts_origin.astimezone(tz_dst)

    # Yes/No DST?
    is_dst = bool(dst_zone.dst())

    # Now we know what timezone the server was in during that time, based on the dst
    server_tz = pytz.timezone("Etc/GMT-3" if is_dst else "Etc/GMT-2")

    # Now convert the timestamp to server_tz
    server_ts = ts_origin.astimezone(server_tz)

    # Return as a string (will be back-converted in calling function)
    return server_ts.strftime('%Y-%m-%d %H:%M:%S')
