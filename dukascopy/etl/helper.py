import copy
import yaml
from dataclasses import asdict
from typing import Dict, Tuple, Optional
from pathlib import Path
from datetime import datetime, time, timedelta
from datetime import datetime, timedelta
from config.app_config import AppConfig, ResampleConfig, ResampleSymbol, ResampleSymbolTradingSession

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

def resample_calculate_sessions_for_date(current_date, config):
    """
    Calculates session boundaries in MT4 Server Time based on 
    localized session definitions (e.g., Australia/Sydney).
    """
    tz_local = zoneinfo.ZoneInfo(config.timezone) # Australia/Sydney

    # TODO: fix timezone for MT4 server retrieval, currently fixed value
    tz_server = zoneinfo.ZoneInfo("Etc/GMT-2")    # Example MT4 Server (Fixed Offset) (watchout, posix GMT!)
    
    sessions_for_day = []

    for session_name, session_item in config.sessions.items():
        for range_name, range_item in session_item.ranges.items():
            # 1. Create localized start/end datetimes
            start_local = datetime.combine(current_date, 
                                          datetime.strptime(range_item.from_time, "%H:%M").time(), 
                                          tzinfo=tz_local)
            end_local = datetime.combine(current_date, 
                                        datetime.strptime(range_item.to_time, "%H:%M").time(), 
                                        tzinfo=tz_local)

            # 2. Handle Overnight ranges (e.g., 17:10 to 07:00)
            if end_local <= start_local:
                end_local += timedelta(days=1)

            # 3. Convert to Server Time (MT4)
            # This automatically handles the DST difference between Sydney and Server
            start_server = start_local.astimezone(tz_server)
            end_server = end_local.astimezone(tz_server)

            sessions_for_day.append({
                "name": session_name,
                "range": range_name,
                "start": start_server.replace(tzinfo=None), # Strip tz for comparison
                "end": end_server.replace(tzinfo=None)
            })
            

    print(yaml.safe_dump(sessions_for_day,
        default_flow_style=False,
        sort_keys=False,))
    # we are not done yet, just invalid statement to break
    os.exit
    return sessions_for_day

def resample_get_timestamp_from_line(line: str) -> datetime:
    """
    Extracts timestamp from a line formatted as:
    YYYY-MM-DD HH:MM:SS,open,high,low,close,volume...
    """
    try:
        # Extract the first 19 characters (length of YYYY-MM-DD HH:MM:SS)
        # This is faster than splitting the whole line if the line is long.
        dt_str = line[:19]
        
        # Use fromisoformat for near-native parsing speed
        return datetime.fromisoformat(dt_str)
        
    except ValueError:
        # Handles cases like headers or empty lines
        return None


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


def resample_resolve_paths(
    symbol: str,
    ident: str,
    data_path: Path,
    config: ResampleConfig,
) -> Tuple[Optional[Path], Path, Path, bool]:
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


def resample_get_symbol_config(symbol: str, app_config: AppConfig) -> ResampleSymbol:
    """
    Build and return the fully merged resample configuration for a single symbol.

    The merge order is:
        1. Global resample configuration
        2. Symbol-level overrides
        3. Session-level overrides
        4. skip_timeframes (absolute priority, applied last)

    The returned object is a ResampleSymbol containing resolved
    primitives, timeframes, and sessions ready for consumption by the
    resampling engine.

    Parameters
    ----------
    symbol : str
        Trading symbol identifier (e.g. "AUS.IDX-AUD").
    app_config : AppConfig
        Root application configuration.

    Returns
    -------
    ResampleSymbol
        The resolved symbol configuration including session-aware timeframes.
    """
    # Copy the global resample configuration to avoid mutating the source config
    global_config: ResampleConfig = app_config.resample
    merged_config: ResampleConfig = copy.deepcopy(global_config)

    # Ensure a symbol override always exists to simplify merge logic
    if not merged_config.symbols.get(symbol):
        merged_config.symbols.update({symbol: ResampleSymbol()})

    # Fetch the symbol override instance
    symbol_override: ResampleSymbol = merged_config.symbols.get(symbol)

    # Resolve primitive overrides, falling back to global defaults
    symbol_override.round_decimals = (
        symbol_override.round_decimals or merged_config.round_decimals
    )
    symbol_override.batch_size = (
        symbol_override.batch_size or merged_config.batch_size
    )

    # Build the symbol-level timeframe set:
    # global timeframes first, symbol overrides on top
    base_timeframes = copy.deepcopy(merged_config.timeframes)
    base_timeframes.update(symbol_override.timeframes)
    symbol_override.timeframes = base_timeframes

    # Merge session-specific timeframes on top of symbol-level timeframes
    if symbol_override.sessions:
        for ident, session in symbol_override.sessions.items():
            # Start from the fully resolved symbol timeframes
            s_timeframes = copy.deepcopy(symbol_override.timeframes)
            # Apply session-specific overrides
            s_timeframes.update(session.timeframes)
            # Persist the merged result back into the session
            session.timeframes = s_timeframes
    else:
        # Create a default 24h session if none are defined
        from config.app_config import (
            ResampleSymbolTradingSession,
            ResampleSymbolTradingSessionRange,
        )

        default_range = ResampleSymbolTradingSessionRange(
            from_time="00:00:00",
            to_time="23:59:59",
        )
        default_session = ResampleSymbolTradingSession(
            timeframes=copy.deepcopy(symbol_override.timeframes),
            ranges={"default": default_range},
        )
        symbol_override.sessions = {"default": default_session}

    # Apply skip_timeframes with absolute priority across all scopes
    if symbol_override.skip_timeframes:
        for tf_key in symbol_override.skip_timeframes:
            # Remove from global view
            merged_config.timeframes.pop(tf_key, None)
            # Remove from symbol-level view
            symbol_override.timeframes.pop(tf_key, None)
            # Remove from all session-level views
            for session in symbol_override.sessions.values():
                session.timeframes.pop(tf_key, None)

    return symbol_override
