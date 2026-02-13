from datetime import datetime, timedelta
import pytz

TZ_CONFIG = {
    "America/New_York": {
        # Map UTC offset (minutes) -> Shift (ms)
        "shifts": {-240: 10800000, -300: 7200000}, 
        "symbols": ["BTC-USD", "*"] # BTC is always here, * captures the rest
    },
    "Etc/UTC": {
        "shifts": {0: 0},
        "symbols": ["AAPL.US-USD"] # Add specific symbols here if they are in UTC
    }
}

def _marketstate_backend_shift_for_symbol(symbol: str, ts_ms: int) -> int:
    """
    Determines the shift (ms) that WAS applied to a timestamp 
    based on the symbol's assigned timezone and the date.
    """
    # 1. Find the Timezone for the Symbol
    target_tz_name = "America/New_York" # Default/Wildcard fallback
    target_cfg = TZ_CONFIG["America/New_York"]

    # Check explicit assignments first
    for tz_name, cfg in TZ_CONFIG.items():
        if symbol in cfg["symbols"]:
            target_tz_name = tz_name
            target_cfg = cfg
            break
    
    # 2. Determine UTC Offset for that date
    # We use the timestamp to get the date, then check 12:00 noon to avoid DST edge cases
    try:
        # Create a date object from the timestamp (assumed close to 'now')
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=pytz.utc)
        
        # Resolve the timezone
        tz = pytz.timezone(target_tz_name)
        
        # Check noon on this date in the target timezone to find the offset
        # (Using noon avoids the 2am switchover ambiguity)
        dt_noon = datetime(dt.year, dt.month, dt.day, 12, 0, 0)
        tz_aware_dt = tz.localize(dt_noon)
        offset_minutes = int(tz_aware_dt.utcoffset().total_seconds() / 60)

        # 3. Return the mapped shift
        return target_cfg["shifts"].get(offset_minutes, 0)

    except Exception as e:
        # Fallback to 0 if pytz fails or config is missing
        return 0
