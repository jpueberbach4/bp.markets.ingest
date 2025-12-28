 
 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        rexample_post_process.py
 Author:      JP Ueberbach
 Created:     2025-12-28
 Description: Pre- and post-processing utilities for resampled OHLCV data.

              This module provides vectorized preprocessing logic used during
              the resampling pipeline to determine session origins efficiently.
              It replaces the former line-by-line tracker-based approach with
              timezone- and DST-aware batch computations, significantly reducing
              CPU overhead while preserving correctness and crash safety.

              The primary responsibility of this module is to compute accurate
              session origins for higher-timeframe bars, enabling fast generation
              of Panama-adjusted views and other session-sensitive aggregates.

 Usage:
     Imported and invoked by the resampling pipeline.

 Requirements:
     - Python 3.8+
     - pandas
     - pytz

 License:
     MIT License
===============================================================================
"""
import pytz
import pandas as pd
from datetime import datetime, timedelta
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

def get_dst_transitions(start_dt, end_dt, tz_name):
    """Retrieve daylight saving time (DST) transition points within a date range.

    This function returns a list of UTC transition datetimes for the server's
    timezone that fall between the specified start and end datetimes. These
    transitions are used to adjust session origins and timestamps in resampled
    OHLCV data.

    Args:
        start_dt (datetime or str): Start of the date range to check for DST transitions.
        end_dt (datetime or str): End of the date range to check for DST transitions.
        config: Configuration object containing the `server_timezone` attribute.

    Returns:
        List[datetime]: List of UTC datetimes representing DST transitions
            that occur within the specified range.

    """
    # The naming of config.server_timezone is not "completely correct"
    tz = pytz.timezone(tz_name)
    if not hasattr(tz, '_utc_transition_times'):
        return []

    s = pd.Timestamp(start_dt).to_pydatetime().replace(tzinfo=None)
    e = pd.Timestamp(end_dt).to_pydatetime().replace(tzinfo=None)
    # Return transitions that fall within our data range
    return [t for t in tz._utc_transition_times if s <= t <= e]

def resample_pre_process_origin(df: pd.DataFrame, ident, step, config) -> pd.DataFrame:
    """Pre-compute and assign session origins for resampled data using vectorized logic.

    This function determines the correct session origin for each row in a resampled
    OHLCV DataFrame without relying on expensive line-by-line session tracking.
    It accounts for daylight saving time transitions between the server timezone
    and the configured symbol timezone, and applies session-specific origin
    adjustments based on configured session ranges.

    The resulting origin values are written to the ``origin`` column, and all
    intermediate helper columns are removed before returning.

    Args:
        df (pd.DataFrame): Resampled OHLCV data indexed by datetimes.
        ident: Timeframe identifier used to resolve timeframe-specific origins.
        step: Resampling step configuration (currently unused by this function).
        config: Symbol configuration containing timezone, session, and timeframe
            definitions.

    Returns:
        pd.DataFrame: The input DataFrame with a populated ``origin`` column.

    Note: This is a very heavy function. It is this complex because we already shifted
          datetimes in the transform step. However, it's fast (vectorized)

    TODO: Currently, the date is FIXED to America/Newyork, there should be a
          server_timezone setting for the symbol

    """
    # Fast path: only a single default session is configured
    if config.sessions.get('default') and len(config.sessions) == 1:
        df['origin'] = config.sessions.get('default').timeframes.get(ident).origin
        return df

    # Resolve relevant timezones
    tz_sg = pytz.timezone(config.timezone)

    # Naming of "server_timezone" is not fully "correct". Since it only defines
    # on what basis the DST shifts are happening.
    tz_ny = pytz.timezone(config.server_timezone)

    # THIS is the actually timezone of the server IN WINTER!
    tz_server_std = pytz.timezone("Etc/GMT-2")

    # Compute the reference offset gap using current offsets
    ref_now = datetime.now(tz_sg)
    server_now_std = datetime.now(tz_server_std)
    ref_gap = (
        ref_now.utcoffset().total_seconds() -
        server_now_std.utcoffset().total_seconds()
    ) / 3600

    # Determine the datetime span of the data
    first_dt = df.index[0]
    last_dt = df.index[-1]

    # Collect DST transition boundaries for BOTH timezones
    server_transitions = get_dst_transitions(first_dt, last_dt, config.server_timezone)
    local_transitions = get_dst_transitions(first_dt, last_dt, config.timezone)
    
    # Merge and sort all unique boundaries
    boundaries = sorted(list(set([first_dt, last_dt] + server_transitions + local_transitions)))

    # Initialize helper columns used during processing
    df['tz_dt_sg'] = pd.NaT
    df['dst_shift'] = 0
    df['tz_origin'] = "epoch"

    # Process each window between DST boundaries
    for i in range(len(boundaries) - 1):
        start_win, end_win = boundaries[i], boundaries[i + 1]

        # Select rows that fall into the current boundary window
        mask = (df.index >= start_win) & (df.index <= end_win)
        if not mask.any():
            continue

        # Use the midpoint of the window to determine DST state
        mid_p = pd.Timestamp(
            start_win + (end_win - start_win) / 2
        ).to_pydatetime().replace(tzinfo=None)

        # Determine whether New York is in DST for this window
        is_dst = bool(tz_ny.localize(mid_p).dst())
        server_tz_str = "Etc/GMT-3" if is_dst else "Etc/GMT-2"

        # Compute timezone offsets for this window
        window_tz_dt_sg = tz_sg.localize(mid_p)
        tz_server_cur = pytz.timezone(server_tz_str)
        window_tz_dt_server = tz_server_cur.localize(mid_p)

        cur_gap = (
            window_tz_dt_sg.utcoffset().total_seconds() -
            window_tz_dt_server.utcoffset().total_seconds()
        ) / 3600

        # Calculate the DST-induced hour shift for this window
        window_shift = int(ref_gap - cur_gap)

        # Store shift and localized datetimes for all rows in the window
        df.loc[mask, 'dst_shift'] = window_shift
        df.loc[mask, 'tz_dt_sg'] = (
            df.index[mask]
            .tz_localize(server_tz_str, ambiguous='infer')
            .tz_convert(config.timezone)
            .tz_localize(None)
        )

    # Extract local times for session range matching
    sg_times = df['tz_dt_sg'].dt.time

    # Apply session-specific origin adjustments
    for name, session in config.sessions.items():
        if name == "catch-all":
            continue

        # Build a mask for rows that belong to this session
        session_mask = pd.Series(True, index=df.index)
        if session.from_date:
            session_mask &= (df['tz_dt_sg'] >= pd.to_datetime(session.from_date))
        if session.to_date:
            session_mask &= (df['tz_dt_sg'] <= pd.to_datetime(session.to_date))

        # Resolve the base origin for this timeframe
        base_origin_str = session.timeframes.get(ident).origin

        if base_origin_str == "epoch":
            df.loc[session_mask, 'tz_origin'] = "epoch"
            continue

        base_h, base_m = map(int, base_origin_str.split(':'))

        # Apply origin shifts for each configured session range
        for r in session.ranges.values():
            st_t = datetime.strptime(r.from_time, "%H:%M").time()
            en_t = datetime.strptime(r.to_time, "%H:%M").time()

            if st_t <= en_t:
                t_mask = (sg_times >= st_t) & (sg_times <= en_t)
            else:
                t_mask = (sg_times >= st_t) | (sg_times <= en_t)

            m = session_mask & t_mask
            if not m.any():
                continue

            # Adjust the origin hour using the computed DST shift
            adj_h = (base_h + df.loc[m, 'dst_shift'].astype(int)) % 24
            df.loc[m, 'tz_origin'] = (
                adj_h.astype(str).str.zfill(2) + f":{base_m:02d}"
            )


    if False:
        # Debugging
        pd.set_option('display.max_columns', None)
        pd.set_option('display.expand_frame_repr', False)
        # Optional: Ensure the columns don't get truncated if the text is long
        pd.set_option('display.max_colwidth', None)
        pd.set_option('display.max_rows', 250000)
        print(df.head(250000))
        sys.exit(1)


    # Replace unresolved origins with the default timeframe origin
    default_origin = config.timeframes.get(ident).origin
    df['tz_origin'] = df['tz_origin'].replace("epoch", default_origin)

    # Persist the final origin and drop helper columns
    df['origin'] = df['tz_origin']
    df.drop(columns=['tz_dt_sg', 'dst_shift', 'tz_origin'], inplace=True)

    return df
