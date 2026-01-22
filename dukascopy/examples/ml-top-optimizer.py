import requests, json, numpy as np, joblib, os
from sklearn.metrics import precision_score, confusion_matrix

class BpMarketsTopOptimizer:
    def __init__(self, symbol="GBP-USD", timeframe="1d"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        
        # Load the Top-specific engine
        self.model_path = os.path.join(os.getcwd(), f"{self.symbol}-top-engine.pkl")
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            print(f"Optimizing: {self.model_path}")
        else:
            raise FileNotFoundError(f"Top model not found at {self.model_path}. Run the top trainer first.")

    def get_data_chunk(self, after_ms, limit=5000):
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/output/JSONP"
        params = {"limit": limit, "subformat": 3, "order": "asc"}
        try:
            response = requests.get(url, params=params)
            raw_json = response.text.split('(', 1)[1].rsplit(')', 1)[0]
            return json.loads(raw_json)['result']
        except: return None

    def prepare_features(self, res):
        # 1. Feature Extraction (Must match trainer exactly)
        close = np.array(res['close'])
        open_p = np.array(res['open'])
        high = np.array(res['high'])
        atr = np.array(res['atr_14'])
        
        dist_50 = (close - np.array(res['sma_50'])) / close
        rsi_norm = np.array(res['rsi_14']) / 100.0
        vol_ratio = atr / close
        
        safe_atr = np.where(atr == 0, 0.00001, atr)
        body_strength = (close - open_p) / safe_atr

        X = np.column_stack([dist_50, rsi_norm, vol_ratio, body_strength])
        X = np.nan_to_num(X)

        # 2. Labeling (Ground Truth for TOP Detection)
        y = np.zeros(len(close))
        window = 12 
        for i in range(window, len(close) - window):
            current_high = high[i]
            # Identify a local maximum within a 25-bar window
            local_max = np.max(high[i-window : i+window+1])
            
            # Identify if price dropped after the peak
            future_price = close[i+12]
            required_drop = 0.5 * atr[i]
            
            if (current_high == local_max) and (future_price < current_high - required_drop):
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def optimize(self, start_ms, end_ms):
        print(f"Optimizing Top-Detection Thresholds for {self.symbol}...")
        
        current_after = start_ms
        all_probs = []
        all_y_true = []
        
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y = self.prepare_features(res)
            if len(X) > 0:
                # Get probability for Class 1 (Top)
                probs = self.model.predict_proba(X)
                class_map = {c: i for i, c in enumerate(self.model.classes_)}
                idx_top = class_map.get(1)
                
                if idx_top is not None:
                    all_probs.extend(probs[:, idx_top])
                    all_y_true.extend(y)
            
            current_after = res['time'][-1]
            
        all_probs = np.array(all_probs)
        all_y_true = np.array(all_y_true)

        print("\n" + "="*50)
        print(f"{'THRESHOLD':<10} | {'SIGNALS':<10} | {'PRECISION':<10} | {'SUCCESSFUL TOPS':<15}")
        print("="*50)

        # Test varying confidence levels to find the sniper "sweet spot"
        for t in [0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
            y_pred = (all_probs > t).astype(int)
            signals = np.sum(y_pred)
            if signals > 0:
                prec = precision_score(all_y_true, y_pred, pos_label=1, zero_division=0)
                cm = confusion_matrix(all_y_true, y_pred)
                winners = cm[1][1] if len(cm) > 1 else 0
                print(f"{t:<10.2f} | {signals:<10} | {prec:<10.2%} | {winners:<15}")
            else:
                print(f"{t:<10.2f} | 0          | 0.00%      | 0")

# Run Optimization on historical data
optimizer = BpMarketsTopOptimizer("GBP-USD", "1d")
optimizer.optimize(start_ms=1420070400000, end_ms=1768880340000)