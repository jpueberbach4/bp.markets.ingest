from generators.sidetracking.base import IAdjustmentStrategy, TimeWindowAction
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
import json
import re

class DukascopyPanamaStrategy(IAdjustmentStrategy):
    """
    Fetches rollover calendar from Dukascopy and calculates cumulative
    back-adjustment windows (Panama method).
    """
    
    BASE_URL = "https://freeserv.dukascopy.com/2.0/"
    
    def __init__(self):
        self.csv_date_fmt = "%d-%b-%y"
        self.target_columns = ["open", "high", "low", "close"]

    def _normalize_payload(self, data: str, symbol: str) -> List[Dict[str, Any]]:
        """
        Internal helper: Unwraps JSONP, filters by symbol, and returns dicts.
        Keeps logic strictly from your original 'normalize_data' function.
        """
        data = data.strip()

        if data.startswith("_callbacks____qmjn9av6ydd"):
            match = re.search(r"_callbacks____qmjn9av6ydd\((.*)\)", data, re.DOTALL)
            if match:
                data = match.group(1)
            else:
                return []

        try:
            json_data = json.loads(data)
        except json.JSONDecodeError as e:
            raise e

        if not json_data:
            return []

        api_symbol = "/".join(symbol.rsplit("-", 1))

        filtered_rows = [
            row for row in json_data
            if str(row.get("title", "")).strip().casefold() == api_symbol.strip().casefold()
        ]

        return filtered_rows

    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Performs the HTTP Request to Dukascopy with correct headers.
        """
        print(f"[*] Fetching remote data for {symbol}...")
        
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "referer": "https://freeserv.dukascopy.com/2.0/?path=cfd_monthly_adjustment/index&header=false",
        }

        params = {
            "path": "cfd_monthly_adjustment/getData",
            "start": "0000000000000",
            "end": "2006745599999",
            "jp": "0",
            "jsonp": "_callbacks____qmjn9av6ydd",
        }

        try:
            response = requests.get(
                self.BASE_URL, 
                headers=headers, 
                params=params, 
                timeout=15
            )
            response.raise_for_status()
            
            return self._normalize_payload(response.text, symbol)

        except requests.RequestException as e:
            print(f"[!] Network error fetching data: {e}")
            return []

    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        """
        Calculates the cumulative offset (Panama Shift).
        """
        if not raw_data:
            return []

        events = []
        for row in raw_data:
            if not row.get('date') or row.get('short') is None:
                continue
            try:
                dt = datetime.strptime(row['date'], self.csv_date_fmt)
                gap = float(row['short'])
                events.append({'date': dt, 'gap': gap})
            except ValueError:
                continue

        events.sort(key=lambda x: x['date'])

        # We start with the SUM of all gaps (Total Offset) applied to the oldest data.
        # As we move forward in time past a rollover, we subtract that rollover's gap.        
        total_cumulative = sum(e['gap'] for e in events)
        current_offset = total_cumulative
        
        actions = []
        
        # Arbitrary start date for the very first window
        prev_date = datetime(2000, 1, 1, 0, 0, 0)

        for i, event in enumerate(events):
            roll_date = event['date']
            
            # Window ends exactly before the rollover day implies new contract
            # (Adjust logic here if your specific rollover happens EOD or BOD)
            window_end = roll_date.replace(hour=23, minute=59, second=59)

            if window_end > prev_date:
                action = TimeWindowAction(
                    id=f"panama-roll-{i+1:03d}",
                    action="-", 
                    columns=list(self.target_columns),
                    value=round(current_offset, 6),
                    from_date=prev_date,
                    to_date=window_end
                )
                actions.append(action)

            # Decrement offset for the next window
            current_offset -= event['gap']
            
            # Next window starts the day after this rollover
            prev_date = (roll_date + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        
        return actions