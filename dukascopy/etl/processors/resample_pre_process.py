 
 
import pytz
import pandas as pd
from datetime import datetime, timedelta
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

def get_dst_transitions(start_dt, end_dt):
    tz = pytz.timezone('America/New_York')
    s = pd.Timestamp(start_dt).to_pydatetime().replace(tzinfo=None)
    e = pd.Timestamp(end_dt).to_pydatetime().replace(tzinfo=None)
    return [t for t in tz._utc_transition_times if s <= t <= e]

def preprocess_origin(tz:str, df: pd.DataFrame, ident, config) -> pd.DataFrame:
    # This is very heavy stuff. If you change this, make sure you know what you are doing
    # This is an attempt to eliminate the line-by-line session determination in resample_batch
    # I made it myself VERY difficult by not keeping the original UTC times.
    # Now i need to backconvert. Making this routine extremely complex.
    # Commenting it line by line in order to not "lose grip"

    tz_sg = pytz.timezone(tz)
    tz_ny = pytz.timezone('America/New_York')       # Change this
    tz_server_std = pytz.timezone("Etc/GMT-2")      # Change this
    
    ref_now = datetime.now(tz_sg)
    server_now_std = datetime.now(tz_server_std)
    ref_gap = (ref_now.utcoffset().total_seconds() - 
            server_now_std.utcoffset().total_seconds()) / 3600

    first_dt = df.index[0]
    last_dt = df.index[-1]

    # Get the DST transitions in UTC
    transitions = get_dst_transitions(first_dt, last_dt)

    # Determine boundary windows for the DST switches
    boundaries = sorted(list(set([first_dt, last_dt] + transitions)))
    
    df['tz_dt_sg'] = pd.NaT
    df['dst_shift'] = 0
    df['tz_origin'] = "epoch"

    # For each of the DST transition windows
    for i in range(len(boundaries) - 1):
        # Get the start and end of the window
        start_win, end_win = boundaries[i], boundaries[i+1]

        # Get a mask that marks all dates with this window
        mask = (df.index >= start_win) & (df.index <= end_win)

        # If any date did not confirm the mask
        if not mask.any(): continue
        
        # Get the middle of the window to determine the DST status for this window
        mid_p = pd.Timestamp(start_win + (end_win - start_win) / 2).to_pydatetime().replace(tzinfo=None)
        is_dst = bool(tz_ny.localize(mid_p).dst())

        # Change this, should be based on offset_shift_map (if we want to support "exotic" metatrader servers)
        server_tz_str = "Etc/GMT-3" if is_dst else "Etc/GMT-2"
        tz_server_cur = pytz.timezone(server_tz_str)
        server_now_cur = datetime.now(tz_server_cur) 

        # Determine the current GAP
        cur_gap = (ref_now.utcoffset().total_seconds() - 
                server_now_cur.utcoffset().total_seconds()) / 3600
        
        # For this window, the shift is this amount in hours
        window_shift = int(ref_gap - cur_gap)

        # Set the window_shift as a column (for debugging) for this boundary
        df.loc[mask, 'dst_shift'] = window_shift

        # Convert the datetime column into a new column having the correctly shifted self.config.timezone date
        df.loc[mask, 'tz_dt_sg'] = (df.index[mask]
                                    .tz_localize(server_tz_str, ambiguous='infer')
                                    .tz_convert(tz)
                                    .tz_localize(None))

    # Get the localized times
    sg_times = df['tz_dt_sg'].dt.time
    
    for name, session in config.sessions.items():
        if name == "catch-all": continue

        # Get a fullmask
        session_mask = pd.Series(True, index=df.index)
        if session.from_date:
            # And filter the mask to only have dates after from_date (inclusive)
            session_mask &= (df['tz_dt_sg'] >= pd.to_datetime(session.from_date))
        if session.to_date:
            # And filter the mask to only have dates before to_date (inclusive)
            session_mask &= (df['tz_dt_sg'] <= pd.to_datetime(session.to_date))

        # Now get the origin for the timeframe with the current ident
        base_origin_str = session.timeframes.get(ident).origin

        # TODO: we should break here, but because of debugging we continue
        if base_origin_str == "epoch":
            df.loc[session_mask, 'tz_origin'] = "epoch"
            continue
        
        # Now get the base hour and base minute from the timeframe configured origin
        base_h, base_m = map(int, base_origin_str.split(':'))

        for r in session.ranges.values():
            # Get time objects from the range
            st_t = datetime.strptime(r.from_time, "%H:%M").time()
            en_t = datetime.strptime(r.to_time, "%H:%M").time()
            
            # Get the mask for the range, locate matches in df
            t_mask = (sg_times >= st_t) & (sg_times <= en_t) if st_t <= en_t \
                    else (sg_times >= st_t) | (sg_times <= en_t)
            
            # Filter the session_mask with the range mask
            m = session_mask & t_mask

            # If we did not have any mask matches, this session range does not apply, move on to the next one
            if not m.any(): continue

            # AH! we have matches, now start applying the shift to the origin
            adj_h = (base_h + df.loc[m, 'dst_shift'].astype(int)) % 24
            
            # Apply the shift and store adjusted origin to tz_origin column
            df.loc[m, 'tz_origin'] = (adj_h.astype(str).str.zfill(2) + f":{base_m:02d}") # Change this to origin column


    # Change: tz_origin is debug column, should become origin
    # Change: drop tz_origin, dst_shift and tz_dt_sg columns from data frame
    # Jesus. What a routine. Sweating. OMG.

    pd.set_option('display.max_columns', None)
    pd.set_option('display.expand_frame_repr', False)
    # Optional: Ensure the columns don't get truncated if the text is long
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_rows', 250000)
    print(df.head(250000))

    sys.exit(1)
    return df