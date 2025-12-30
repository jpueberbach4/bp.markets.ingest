import duckdb
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from pathlib import Path
import requests
import time
import json
import csv
import io
import re

CACHE_MAX_AGE = 86400
CACHE_PATH = "data/rollover"

# Dukascopy CSV schema: column names and types
DUKASCOPY_CSV_SCHEMA = {
    "time": "TIMESTAMP",
    "open": "DOUBLE",
    "high": "DOUBLE",
    "low": "DOUBLE",
    "close": "DOUBLE",
    "volume": "DOUBLE",
}

# Standard CSV timestamp format for parsing
CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

def normalize_data(data:str, symbol:str) -> Optional[str]:
    # Strip trailing and leading spaces
    data = data.strip()
    # Make JSONP JSON
    if data.startswith("_callbacks____qmjn9av6ydd"):
        match = re.search(r'_callbacks____qmjn9av6ydd\((.*)\)', data, re.DOTALL)
        if match:
            data = match.group(1)
        else:
            return None

    # Load the JSON data
    json_data = json.loads(data)

    if json_data:
        # Normalize the symbol
        symbol = "/".join(symbol.rsplit('-', 1))
        # Setup the StringIO
        sio = io.StringIO()
        # Filter for the symbol
        json_data = [
            row for row in json_data 
            if str(row.get('title', '')).strip().casefold() == symbol.strip().casefold()
        ]

        if not json_data:
            return None

        # Sort on data ascending
        json_data.sort(key=lambda x: datetime.strptime(x['date'], '%d-%b-%y'))
        # Make date first row
        headers = ['date'] + [k for k in json_data[0].keys() if k != 'date']
        # Create a CSV and write it to our sio StringIO
        (writer := csv.DictWriter(sio, fieldnames=headers)).writeheader()
        writer.writerows(json_data)
        # Return the value as string
        return sio.getvalue()
    
    # We didnt have any data we could compile
    return None

def fetch_rollover_data_for_symbol(symbol) -> Optional[str]:
    # check cache first
    cache_path = Path(f"{CACHE_PATH}/{symbol}.csv")
    if cache_path.exists() and (cache_path.stat().st_mtime+CACHE_MAX_AGE) > int(time.time()):
        # return the cache_path (for direct loading in duckdb)
        return cache_path
        
    url = "https://freeserv.dukascopy.com/2.0/"
    try:
        # Perform HTTP request
        response = requests.Session().get(
            url,
            headers = {
                    "accept": "*/*",
                    "accept-language": "en-US,en;q=0.9",
                    "cache-control": "no-cache",
                    "pragma": "no-cache",
                    "accept-encoding": "gzip, deflate",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "referer": "https://freeserv.dukascopy.com/2.0/?path=cfd_monthly_adjustment/index&header=false&tableBorderColor=%23D92626&highlightColor=%23FFFAFA&currency=USD&amount=1&width=100%25&height=500&adv=popup&lang=en",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "script",
                    "sec-fetch-mode": "no-cors",
                    "sec-fetch-site": "same-origin"
            },
            params = {
                "path": "cfd_monthly_adjustment/getData",
                "start": "0000000000000",
                "end": "2006745599999",                     # very much in advance
                "jp": "0",
                "jsonp": "_callbacks____qmjn9av6ydd"
            },
            timeout=10,
        )
        response.raise_for_status()
        # Todo: if timeout and cache exists, return the cache
        
        # Normalize the data
        normalized_data = normalize_data(response.text, symbol)

        if not normalized_data:
            return None

        # Write the cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f_cache:
            f_cache.write(normalized_data)

        # Return the cache_path (for direct loading to duckdb)
        return cache_path

    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, "status_code", 0)
        if cache_path.exists():
            print("Warning: Refresh of symbol rollover calendar failed. Using old version.")
            return cache_path
        # Else raise
        raise

    return None


def adjust_symbol(symbol, input_filepath, output_filepath):
    # TODO: parameterize this and map it to configuration
    rollover_filepath = fetch_rollover_data_for_symbol(symbol)

    if not rollover_filepath:
        print(f"Warning: Couldn't find a rollover calendar for {symbol}. Skipping Panama-adjustment.")
        return False

    print(f"Warning: panama modifier set for {symbol}. Handling rollover gaps...")

    adjust_sql = f"""
        CREATE OR REPLACE TABLE adjustments AS
        WITH roll_diffs AS (
            SELECT 
                (strptime(date, '%d-%b-%y')::DATE + INTERVAL '23 hours 59 minutes 59 seconds')::TIMESTAMP as roll_date,
                (long::DOUBLE) * -1 as adj_value 
            FROM read_csv('{rollover_filepath}', header=True)
        ),
        cumulative AS (
            SELECT 
                roll_date,
                SUM(adj_value) OVER (ORDER BY roll_date DESC) as total_offset
            FROM roll_diffs
        )
        SELECT * FROM cumulative;

        COPY (
            WITH raw_data AS (
                SELECT 
                    strptime(CAST(time AS VARCHAR), '{CSV_TIMESTAMP_FORMAT}') AS ts,
                    open::DOUBLE as o,
                    high::DOUBLE as h,
                    low::DOUBLE as l,
                    close::DOUBLE as c,
                    volume::DOUBLE as v
                FROM read_csv('{input_filepath}', header=True)
            )
            SELECT 
                strftime(raw_data.ts, '{CSV_TIMESTAMP_FORMAT}') AS time,
                round(o + COALESCE(adj.total_offset, 0), 6) as open,
                round(h + COALESCE(adj.total_offset, 0), 6) as high,
                round(l + COALESCE(adj.total_offset, 0), 6) as low,
                round(c + COALESCE(adj.total_offset, 0), 6) as close,
                v as volume
            FROM raw_data
            ASOF LEFT JOIN adjustments adj ON raw_data.ts <= adj.roll_date
            ORDER BY raw_data.ts ASC
        ) TO '{output_filepath}' (HEADER True, DELIMITER ',');
    """
    con = duckdb.connect(database=":memory:")
    con.execute(adjust_sql)
    con.close()
    return True


def fork_panama(
    task: Tuple[str, str, str, str, str, str, Dict[str, Any], Any]
) -> Tuple[str, str, str, str, str, str, Dict[str, Any]]:
    """Prepare a symbol task for processing, optionally handling adjusted data.

    This function unpacks a task tuple describing a symbol processing job.
    If the task includes the `"adjusted"` modifier, the function is intended
    to prepare adjusted timeframe data by generating or reusing temporary
    adjusted files and updating task paths accordingly. If no adjustment is
    required, the task is returned unchanged.

    Args:
        task: A tuple containing:
            - symbol (str): Symbol identifier (e.g., ticker or instrument name).
            - timeframe (str): Target timeframe (e.g., "1m", "5m", "1h").
            - input_filepath (str): Path to the input data file.
            - after_str (str): Start time constraint as a string.
            - until_str (str): End time constraint as a string.
            - modifiers (str): Modifier flags (e.g., includes "adjusted").
            - options (Dict[str, Any]): Additional processing options.

    Returns:
        A task tuple with the same structure as the input. If adjustment logic
        is applied, the returned tuple may contain modified file paths and/or
        options reflecting the adjusted data preparation.
    """

    symbol, timeframe, input_filepath, after_str, until_str, modifiers, options = task

    if "panama" in modifiers:
        from filelock import FileLock, Timeout
        from etl.config.app_config import load_app_config, resample_get_symbol_config, ResampleConfig
        from etl.resample import fork_resample
        # Get symbol configuration for Resampler
        config = resample_get_symbol_config(
            symbol,
            app_config := load_app_config(options['config_file']) 
        )
        # Nobody overrides root config frame, so get the source path directly (no complex logic)
        raw_base_path, adjusted_base_path, lock_path, tf_path = [
            Path(config.timeframes.get("1m").source) / f"{symbol}.csv",
            Path(options.get('output_dir')).parent / f"adjust/1m/{symbol}.csv",
            Path(options.get('output_dir')).parent / f"locks/{symbol}.lck",
            Path(options.get('output_dir')).parent / f"adjust/{timeframe}/{symbol}.csv",
        ]
        # Create directories
        adjusted_base_path.parent.mkdir(parents=True,exist_ok=True)
        lock_path.parent.mkdir(parents=True,exist_ok=True)

        # Dry-run
        if options.get('dry_run'):
            print(f"DRY-RUN: Would have performed Panama adjustment for {symbol}...")
            input_filepath = tf_path
            task = (symbol, timeframe, input_filepath, after_str, until_str, modifiers, options)
            return task

        # Acquire exclusive filelock, no simultaneous adjustment logic for same symbol
        lock = FileLock(lock_path)
        try:
            lock.acquire(timeout=300)
            # We acquired the lock, continue
        except Timeout:
            print(f"Something is wrong. We couldnt acquire a lockfile {lock_path}. Exiting.")
            sys.exit(1)    
        
        # Check if we already have an adjusted file for this tf (adjust/tf/symbol.csv)
        if not adjusted_base_path.exists():
            # It was not already prepared in another parallel process
            # Now, prepare the adjusted 1m file and account for the rollover gaps, CALL adjust.adjust_symbol
            if not adjust_symbol(symbol, raw_base_path, adjusted_base_path):
                return  task
            # Adjust the 1m base timeframe source in root (defaults is enough for the moment)
            app_config.resample.timeframes.get("1m").source = str(adjusted_base_path.parent)
            # Now, adjust resample.paths.data in app_config, set to tempdir/adjust (tf's directly below)
            app_config.resample.paths.data = str(tf_path.parent.parent)
            # CALL the fork_resample(symbol, app_config)
            print(f"Warning: panama modifier set for {symbol}. Resampling...")
            fork_resample([symbol, app_config])
            # Todo: exception handling and such
        
        # We are done here, now set input_filepath to tf_path
        input_filepath = tf_path

        # And release the lock...
        lock.release()

        # Return the adjusted task so fork_extract can continue with regular process
        task = (symbol, timeframe, input_filepath, after_str, until_str, modifiers, options)

    return task