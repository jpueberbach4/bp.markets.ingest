import requests, json, numpy as np, time, joblib, os
from sklearn.ensemble import RandomForestClassifier

class BpMarketsTopTrainer:
    def __init__(self, symbol="GBP-USD", timeframe="1d"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)" 
        
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10, 
            class_weight='balanced',
            random_state=42,
            n_jobs=-1 
        )

    def get_data_chunk(self, after_ms, limit=5000):
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/output/JSONP"
        params = {"limit": limit, "subformat": 3, "order": "asc"}
        try:
            response = requests.get(url, params=params)
            raw_json = response.text.split('(', 1)[1].rsplit(')', 1)[0]
            return json.loads(raw_json)['result']
        except: return None

    def prepare_features(self, res):
        close = np.array(res['close'])
        open_p = np.array(res['open'])
        high = np.array(res['high']) # Using Highs for Tops
        atr = np.array(res['atr_14'])
        
        # --- ROBUST FEATURES ---
        dist_50 = (close - np.array(res['sma_50'])) / close
        rsi_norm = np.array(res['rsi_14']) / 100.0
        vol_ratio = atr / close
        safe_atr = np.where(atr == 0, 0.00001, atr)
        body_strength = (close - open_p) / safe_atr # Positive = Green, Negative = Red

        X = np.column_stack([dist_50, rsi_norm, vol_ratio, body_strength])
        X = np.nan_to_num(X)

        # --- LABELS (TOP DETECTION) ---
        y = np.zeros(len(close))
        window = 12 
        
        for i in range(window, len(close) - window):
            current_high = high[i]
            local_max = np.max(high[i-window : i+window+1])
            is_absolute_high = (current_high == local_max)
            
            # Standard Drop: 0.5 ATR (Price must fall after the high)
            future_price = close[i+12]
            required_drop = 0.5 * atr[i]
            did_drop = future_price < (current_high - required_drop)
            
            if is_absolute_high and did_drop:
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def train_loop(self, start_ms, end_ms):
        current_after = start_ms
        print(f"Collecting Top Data for {self.symbol}...")
        
        all_X, all_y = [], []
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            X, y = self.prepare_features(res)
            if len(X) > 0:
                all_X.append(X); all_y.append(y)
            current_after = res['time'][-1]

        if not all_X: return
        X_train, y_train = np.vstack(all_X), np.concatenate(all_y)
        
        print(f"Training Top Detector on {len(y_train)} bars...")
        print(f"Tops found: {int(np.sum(y_train))}")
        
        self.model.fit(X_train, y_train)
        filename = f"{self.symbol}-top-engine.pkl"
        joblib.dump(self.model, os.path.join(os.getcwd(), filename))
        print(f"SAVED TO: {filename}")

trainer = BpMarketsTopTrainer("GBP-USD", "1d")
trainer.train_loop(start_ms=1514764800000, end_ms=1768880340000)