import fnmatch
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

class IndicatorIngestor:
    def __init__(self, config):
        self.config = config

    def _fetch_ind(self, ind, start_ms):
        url_base = f"{self.config['BASE_URL']}/select/{self.config['SYMBOL']},{self.config['TIMEFRAME']}"
        try:
            res = requests.get(f"{url_base}[{ind}]/after/{start_ms}/output/JSON?limit=5000&subformat=3", timeout=10).json()
            if res['status'] == 'ok' and res['result']:
                df = pd.DataFrame(res['result'])
                cols = {c: f"{ind}___{c}" for c in df.columns if c not in ['time','open','high','low','close','volume']}
                return df.rename(columns=cols)[['time'] + list(cols.values())]
        except:
            return None

    def get_data(self):
        print("🔍 [Ingest] Fetching Indicator Universe...")
        r = requests.get(f"{self.config['BASE_URL']}/list/indicators/output/JSON").json()['result']
        
        universe = []
        for k, v in r.items():
            if any(fnmatch.fnmatch(k.lower(), p.lower()) for p in self.config['BLACKLISTED_INDICATORS']):
                continue
            defaults = v.get('defaults', {})
            params = [str(val) for val in defaults.values() if str(val).replace('.','',1).isdigit()]
            universe.append(f"{k}_{'_'.join(params)}" if params else k)
        
        universe = list(set(universe + self.config['FORCED_INDICATORS']))
        start_ms = int(datetime.strptime(self.config['START_DATE'], "%Y-%m-%d").timestamp() * 1000)
        
        print(f"🚜 [Ingest] Harvesting {len(universe)} indicators (Parallel)...")
        url_base = f"{self.config['BASE_URL']}/select/{self.config['SYMBOL']},{self.config['TIMEFRAME']}"
        master = pd.DataFrame(requests.get(f"{url_base}[{self.config['TARGET_INDICATOR']}]/after/{start_ms}/output/JSON?limit=5000&subformat=3").json()['result'])
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._fetch_ind, ind, start_ms) for ind in universe]
            for i, future in enumerate(as_completed(futures)):
                if i % 20 == 0: print(f"   Progress: {i}/{len(universe)}...", end="\r")
                res_df = future.result()
                if res_df is not None:
                    master = pd.merge(master, res_df, on='time', how='left')

        print(f"\n⚡ [Ingest] Final Sanitization...")
        
        # Drop common OHLCV columns first
        common_to_drop = ['open', 'high', 'low', 'close', 'volume', 'time']
        master = master.drop(columns=[c for c in common_to_drop if c in master.columns], errors='ignore')

        # IDENTIFY TARGET BEFORE FILTERING
        # We find the target column now, before the blacklist wipes it out.
        target_candidates = [c for c in master.columns if self.config['TARGET_INDICATOR'] in c]
        if not target_candidates:
            print(f"❌ CRITICAL: Target {self.config['TARGET_INDICATOR']} not found in columns!")
            sys.exit(1)
        target_col_name = target_candidates[0]

        # Re-apply the blacklist filter
        # We loop through columns but EXEMPT the target_col_name from being dropped.
        for col in list(master.columns):
            if col == target_col_name: 
                continue # Do not drop the target!
            if any(fnmatch.fnmatch(col.lower(), p.lower()) for p in self.config['BLACKLISTED_INDICATORS']):
                master = master.drop(columns=[col])

        # Proceed with existing sanitization
        master = master.apply(pd.to_numeric, errors='coerce')
        
        # Now drop NaNs and separate features
        master = master.dropna(subset=[target_col_name])
        features = master.drop(columns=[target_col_name]).dropna(axis=1, how='all').fillna(0.0)

        print(f"✅ Sanitize Complete. Features: {len(features.columns)} | Target: {target_col_name}")
        
        return features, master[target_col_name]