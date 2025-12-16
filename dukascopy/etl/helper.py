import copy
import yaml
from dataclasses import asdict
from typing import Dict, Tuple, Optional
from pathlib import Path
from datetime import datetime, time, timedelta, date
from datetime import datetime, timedelta
from config.app_config import AppConfig, ResampleConfig, ResampleSymbol, ResampleSymbolTradingSession, ResampleTimeframe

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo


from datetime import datetime, timedelta

def resample_get_active_origin_from_line(line: str, ident: str, session_name: str, config: 'ResampleSymbol') -> str:
    timestamp = datetime.fromisoformat(line[:19])
    session_cfg = config.sessions.get(session_name)
    timeframe = session_cfg.timeframes.get(ident)
    base_origin_str = timeframe.origin  # e.g., "00:50" (Your "Winter" Baseline)

    if base_origin_str == "epoch":
        return "epoch"

    # 1. Reference point: When the YAML "00:50" was true (Winter)
    ref_date = datetime(2025, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC"))
    
    # 2. Get the Sydney vs Server gap for the REFERENCE date
    tz_sydney = zoneinfo.ZoneInfo(config.timezone)
    tz_server_ref = get_mt4_server_tz(ref_date)
    
    # Gap in Jan (Winter): Sydney(11) - Server(2) = 9 hours
    ref_gap = (datetime.now(tz_sydney).utcoffset().total_seconds() - 
               datetime.now(tz_server_ref).utcoffset().total_seconds()) / 3600

    # 3. Get the Sydney vs Server gap for the CURRENT date
    tz_server_cur = get_mt4_server_tz(timestamp)
    
    # Gap in Aug (Summer): Sydney(10) - Server(3) = 7 hours
    cur_gap = (timestamp.astimezone(tz_sydney).utcoffset().total_seconds() - 
               timestamp.astimezone(tz_server_cur).utcoffset().total_seconds()) / 3600

    # 4. The 'Movement' is the difference between the two gaps
    # Dec -> Aug: 9 hours - 7 hours = 2 hours shift
    shift = int(ref_gap - cur_gap)

    # 5. Apply shift to the YAML base_origin
    base_h, base_m = map(int, base_origin_str.split(':'))
    adjusted_h = (base_h + shift) % 24
    
    return f"{adjusted_h:02d}:{base_m:02d}"

def resample_get_active_session_from_line(line:str, config: ResampleSymbol) -> str:

    # Initialize variables for session-support
    last_date = None
    daily_session_ranges = [] 

    timestamp = datetime.fromisoformat(line[:19])

    # Ensure timestamp is naive if your session "start"/"end" are naive
    current_timestamp_naive = timestamp.replace(tzinfo=None)
    current_date = timestamp.date()

    if current_date != last_date:
        daily_session_ranges = resample_calculate_sessions_for_date(current_date, config)
        last_date = current_date

    # Quick check against the day's pre-calculated boundaries
    active_session_info = None
    
    # Optimized lookup: Accessing dict keys
    current_mins = current_timestamp_naive.hour * 60 + current_timestamp_naive.minute

    for session_entry in daily_session_ranges:
        # Pre-calculate session minutes if not already done in calculate_sessions
        start_mins = session_entry["start"].hour * 60 + session_entry["start"].minute
        end_mins = session_entry["end"].hour * 60 + session_entry["end"].minute
        
        # Logic for Standard Day Range (e.g., 09:50 to 16:30)
        if start_mins <= end_mins:
            is_active = start_mins <= current_mins <= end_mins
        # Logic for Wraparound/Midnight Range (e.g., 17:10 to 07:00)
        else:
            is_active = (current_mins >= start_mins) or (current_mins <= end_mins)

        if is_active:
            active_session_info = session_entry
            break

    if active_session_info is None:
        print(yaml.safe_dump(
            daily_session_ranges,
            default_flow_style=False,
            sort_keys=False,
            )
        )
        raise ValueError(
            f"Line {line} is out_of_market. Your configuration is not OK {symbol}/{ident}"
        )

    return active_session_info["name"]


def get_mt4_server_tz(dt: date) -> zoneinfo.ZoneInfo:
    """
    Returns the MT4 server timezone (GMT+2 or GMT+3) based on 
    whether New York is in Daylight Saving Time on the given date.
    """
    nyc_tz = zoneinfo.ZoneInfo("America/New_York")
    nyc_dt = datetime.combine(dt, time(17, 0)).replace(tzinfo=nyc_tz)
    offset = 3 if nyc_dt.dst() != timedelta(0) else 2
    return zoneinfo.ZoneInfo(f"Etc/GMT-{offset}")

def resample_calculate_sessions_for_date(current_date, config):
    """
    Calculates session boundaries in MT4 Server Time based on 
    localized session definitions (e.g., Australia/Sydney).
    """
    tz_local = zoneinfo.ZoneInfo(config.timezone) # Australia/Sydney
    tz_server = get_mt4_server_tz(current_date)  # Get MT4 server time
    
    sessions_for_day = []

    for session_name, session_item in config.sessions.items():
        for range_name, range_item in session_item.ranges.items():
            start_local = datetime.combine(current_date, 
                                          datetime.strptime(range_item.from_time, "%H:%M").time(), 
                                          tzinfo=tz_local)
            end_local = datetime.combine(current_date, 
                                        datetime.strptime(range_item.to_time, "%H:%M").time(), 
                                        tzinfo=tz_local)

            if end_local <= start_local:
                end_local += timedelta(days=1)

            start_server = start_local.astimezone(tz_server)
            end_server = end_local.astimezone(tz_server)

            sessions_for_day.append({
                "name": session_name,
                "range": range_name,
                "start": start_server.replace(tzinfo=None), # Strip tz for comparison
                "end": end_server.replace(tzinfo=None)
            })
            

    if False: 
        print(yaml.safe_dump(sessions_for_day,
            default_flow_style=False,
            sort_keys=False,)
        )
        os.exit

    return sessions_for_day

def resample_is_default_session(config: ResampleSymbol) -> bool:
    """
    Determine whether a symbol is using the implicit default 24-hour session.

    A session is considered the default session if:
    - It is named "default"
    - It defines a single range named "default"
    - The range spans the full trading day from 00:00:00 to 23:59:59

    Parameters
    ----------
    config : ResampleSymbol
        The resolved resample configuration for a symbol, including its
        trading sessions and time ranges.

    Returns
    -------
    bool
        True if the symbol uses the implicit full-day default session,
        False otherwise.
    """
    # Iterate through all configured sessions for the symbol
    for name, session in config.sessions.items():

        # Only the session named "default" can qualify
        if name == "default":

            # Ensure the default time range exists
            default_range = session.ranges.get("default")
            if not default_range:
                continue

            # Check whether the range spans the full 24-hour day
            if (
                default_range.from_time == "00:00:00"
                and default_range.to_time == "23:59:59"
            ):
                return True

    # No qualifying default session was found
    return False


def resample_resolve_paths(symbol: str, ident: str, data_path: Path, config: ResampleConfig) -> Tuple[Optional[Path], Path, Path, bool]:
    """
    Resolve input, output, and index file paths for a resample timeframe.

    This function determines where the input data should be read from and
    where the resampled output and index files should be written to, based
    on the timeframe configuration and its source dependency.

    Parameters
    ----------
    symbol : str
        Trading symbol being processed (e.g. "AUS.IDX-AUD").
    ident : str
        Timeframe identifier (e.g. "5m", "1h").
    config : ResampleConfig
        Fully merged resample configuration containing all timeframe
        definitions and paths.

    Returns
    -------
    tuple
        (
            input_path: Optional[Path],   # None if this is a root timeframe
            output_path: Path,            # Destination CSV path
            index_path: Path,             # Destination index path
            cascade: bool                 # Whether we should skip (continue) in calling loop
        )
    """
    # Fetch the timeframe configuration for the requested identifier
    timeframe: ResampleTimeframe = config.timeframes.get(ident)

    # Root timeframe: no resampling rule, data comes directly from the source
    if not timeframe.rule:
        root_source = Path(f"{timeframe.source}/{symbol}.csv")
        # Root source must exist or resampling cannot proceed
        if not root_source.exists():
            raise IOError(f"Root source missing for {ident}: {root_source}")

        # No cascading resample required for root timeframes, skip = True
        return None, root_source, Path(), True

    # Identify the source timeframe this resample depends on
    source_tf = config.timeframes.get(timeframe.source)
    if not source_tf:
        raise ValueError(
            f"Timeframe {ident} references unknown source: {timeframe.source}"
        )

    # Determine input path depending on whether the source itself is resampled
    if source_tf.rule is not None:
        input_path = Path(data_path) / timeframe.source / f"{symbol}.csv"
    else:
        input_path = Path(source_tf.source) / f"{symbol}.csv"

    # Output CSV path for the resampled timeframe
    output_path = Path(data_path) / ident / f"{symbol}.csv"

    # Index path used for incremental or partial resampling
    index_path = Path(data_path) / ident / "index" / f"{symbol}.idx"

    # If input data does not exist, cascading resample cannot continue
    if not input_path.exists():
        if VERBOSE:
            tqdm.write(
                f"  No base {ident} data for {symbol} → skipping cascading timeframes"
            )
        raise ValueError(
            f"  No base {ident} data for {symbol} → skipping cascading timeframes"
        )

    # Ensure the output file and its parent directories exist
    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w"):
            pass

    # Valid cascading resample paths resolved
    return input_path, output_path, index_path, False



