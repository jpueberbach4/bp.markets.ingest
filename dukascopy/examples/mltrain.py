import requests, json, numpy as np, time, joblib, os
from sklearn.linear_model import SGDClassifier

# NOTE: No StandardScaler imported. We do it manually to prevent bias.

class BpMarketsTrainer:
    def __init__(self, symbol="EUR-USD", timeframe="1h"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)" 
        
        # LOGISTIC REGRESSION
        # Weights: Finding a bottom (1) is 20x more valuable than silence (0)
        self.model = SGDClassifier(
            loss='log_loss', 
            penalty='l2', 
            alpha=0.01, 
            random_state=42, 
            class_weight={0: 1, 1: 20} 
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
        low = np.array(res['low'])
        
        # --- ZERO-BIAS FEATURE ENGINEERING ---
        # We manually scale features so they are roughly 0.0 to 1.0
        # This prevents "Batch Statistics" from leaking future info
        
        # 1. Distance from SMA50 (Multiplied by 100 for scale)
        # e.g., 1% drop becomes -1.0
        dist_50 = ((close - np.array(res['sma_50'])) / close) * 100.0
        
        # 2. RSI Normalized (0.0 to 1.0)
        rsi_norm = np.array(res['rsi_14']) / 100.0
        
        # 3. Volatility Ratio (Multiplied by 1000 for scale)
        # e.g., 0.1% daily range becomes 1.0
        vol_ratio = (np.array(res['atr_14']) / close) * 1000.0

        # Stack Features
        X = np.column_stack([dist_50, rsi_norm, vol_ratio])
        X = np.nan_to_num(X)

        # --- LABELS: DEFINING THE BOTTOM ---
        # Note: We MUST look ahead to define the label (y), 
        # but the model only gets to see the current features (X).
        y = np.zeros(len(close))
        
        # Window: Lowest low in 24 hours (12 back, 12 forward)
        window = 12 
        
        for i in range(window, len(close) - window):
            current_low = low[i]
            
            # 1. Is this the lowest point in the window?
            local_min = np.min(low[i-window : i+window+1])
            is_absolute_low = (current_low == local_min)
            
            # 2. Did it bounce? (Price 12 bars later > Low + 1.5x ATR)
            # We look for a 1.5x ATR move to confirm it wasn't just noise
            future_price = close[i+12]
            required_bounce = 1.5 * np.array(res['atr_14'])[i]
            did_bounce = future_price > (current_low + required_bounce)
            
            if is_absolute_low and did_bounce:
                y[i] = 1 # True Bottom
        
        # Crop the edges where we can't see the future/past
        return X[window:-window], y[window:-window]

    def train_loop(self, start_ms, end_ms):
        current_after = start_ms
        print(f"Training Zero-Bias Sniper for {self.symbol}...")
        total_found = 0
        
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y = self.prepare_features(res)
            
            if len(X) > 0:
                # No Scaler Fit here. X is already manually scaled.
                self.model.partial_fit(X, y, classes=[0, 1])
                total_found += np.sum(y)
            
            current_after = res['time'][-1]
            print(f"Batch: {time.strftime('%Y-%m-%d', time.gmtime(current_after/1000))} | Found {int(np.sum(y))} Bottoms")
        
        print(f"TOTAL BOTTOMS LEARNED: {int(total_found)}")
        
        # Save ONLY the model (No scaler needed)
        filename = f"{self.symbol}-engine.pkl"
        save_path = os.path.join(os.getcwd(), filename)
        joblib.dump(self.model, save_path)
        print(f"SAVED TO: {save_path}")

# Run training (2015 - 2026)
trainer = BpMarketsTrainer("EUR-USD", "1h")
trainer.train_loop(start_ms=1420070400000, end_ms=1768880340000)