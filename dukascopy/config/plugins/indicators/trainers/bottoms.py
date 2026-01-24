import requests, json, numpy as np, time, joblib, os
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier

class BpMarketsTrainer:
    def __init__(self, symbol="EUR-USD", timeframe="1h", save_path="../models"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        self.save_path = save_path 
        
        # STANDARD RANDOM FOREST
        # This is the industry standard for classification.
        # n_estimators=200: Uses 200 "brains" to vote.
        # max_depth=10: Enough depth to see patterns, not enough to memorize noise.
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
        low = np.array(res['low'])
        
        # --- ROBUST FEATURES (Zero-Bias Math) ---
        # 1. Trend Deviation (Where are we relative to the average?)
        dist_50 = (close - np.array(res['sma_50'])) / close
        
        # 2. RSI Normalized (0.0 to 1.0)
        rsi_norm = np.array(res['rsi_14']) / 100.0
        
        # 3. Volatility Ratio (How big are the moves?)
        atr = np.array(res['atr_14'])
        vol_ratio = atr / close
        
        # 4. Candle Body Strength (Green or Red?)
        # (Close - Open) / ATR
        safe_atr = np.where(atr == 0, 0.00001, atr)
        body_strength = (close - open_p) / safe_atr

        X = np.column_stack([dist_50, rsi_norm, vol_ratio, body_strength])
        X = np.nan_to_num(X)

        # --- LABELS ---
        y = np.zeros(len(close))
        window = 12 
        
        for i in range(window, len(close) - window):
            current_low = low[i]
            local_min = np.min(low[i-window : i+window+1])
            is_absolute_low = (current_low == local_min)
            
            # Standard Bounce: 0.5 ATR (Realistic, not impossible)
            future_price = close[i+12]
            required_bounce = 0.5 * atr[i]
            did_bounce = future_price > (current_low + required_bounce)
            
            if is_absolute_low and did_bounce:
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def train_loop(self, start_ms, end_ms):
        current_after = start_ms
        print(f"Collecting Data for {self.symbol}...")
        
        all_X = []
        all_y = []
        
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y = self.prepare_features(res)
            if len(X) > 0:
                all_X.append(X)
                all_y.append(y)
            
            current_after = res['time'][-1]

        if not all_X: return

        X_train = np.vstack(all_X)
        y_train = np.concatenate(all_y)
        
        print(f"Training Random Forest on {len(y_train)} bars...")
        print(f"Bottoms found: {int(np.sum(y_train))}")
        
        self.model.fit(X_train, y_train)
        
        # Save as standard 'engine.pkl'
        filename = f"{self.symbol}-{self.tf}-bottom-engine.pkl"
        save_path = os.path.join(self.save_path, filename)
        joblib.dump(self.model, save_path)
        print(f"SAVED TO: {save_path}")


assets = [
    'AUD-USD',
    'EUR-USD',
    'EUR-NZD',
    'GBP-USD',
    'NZD-USD',
    'USD-CAD',
    'USD-CHF',
    'USD-JPY',
    'XAU-USD'
]

# Train up until now - 7 days back
now = datetime.now(timezone.utc)
two_days_ago = now - timedelta(days=7)
until_ms = int(two_days_ago.timestamp() * 1000)

# After 2018-01-01
after_ms = 1514764800000

for asset in assets:
    print(f"Training for asset {asset}...")
    save_path = Path(__file__).resolve().parent.parent / "models"
    trainer = BpMarketsTrainer(asset, "1d", save_path)
    # Train on recent history (2018-2026)
    trainer.train_loop(start_ms=after_ms, end_ms=until_ms)