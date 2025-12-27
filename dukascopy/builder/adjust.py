import duckdb
from typing import Optional
from datetime import datetime
from pathlib import Path
import requests
import json
import csv
import io
import re


CACHE_MAX_AGE = 86400
CACHE_PATH = "data/rollover"

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

def fetch_data(symbol) -> Optional[str]:
    # check cache first
    cache_path = Path(f"{CACHE_PATH}/{symbol}.csv")
    if cache_path.exists() and (cache_path.stats().m_time+CACHE_MAX_AGE) < int(time.time()):
        # return the cache
        with open(cache_path, "r") as f_cache:
            return f_cache.read()

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
                "end": "1806745599999",
                "jp": "0",
                "jsonp": "_callbacks____qmjn9av6ydd"
            },
            timeout=10,
        )
        response.raise_for_status()
        # Todo: if timeout and cache exists, return the cache
        
        # Normalize the data
        normalized_data = normalize_data(response.text, symbol)

        # Write the cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f_cache:
            f_cache.write(normalized_data)

        # Todo: return the cache_path instead
        return normalized_data

    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, "status_code", 0)
        raise

    return None


def adjust_symbol(symbol):
    print(symbol)
    data = fetch_data(symbol)
    print(data)
    # have a look into the cache
    # do we have the file already?
    # older than config.max_age? 
    # repull from broker
    # extract dates for instrument
    # detect gap end of day, register
    # back-apply difference
    # something for tomorrow
    pass

