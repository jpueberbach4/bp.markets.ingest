import requests, json, numpy as np, joblib, os
from sklearn.metrics import precision_score, confusion_matrix

class BpMarketsOptimizer:
    def __init__(self, symbol="EUR-USD", timeframe="1h"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        
        self.model_path = os.path.join(os.getcwd(), f"{self.symbol}-engine.pkl")
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else: raise FileNotFoundError("Model not found")

    def get_data_chunk(self, after_ms, limit=5000):
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/output/JSONP"
        params = {"limit": limit, "subformat": 3, "order": "asc"}
        try:
            response = requests.get(url, params=params)
            raw_json = response.text.split('(', 1)[1].rsplit(')', 1)[0]
            return json.loads(raw_json)['result']
        except: return None

    def prepare_features(self, res):
        # EXACT MATCH TO TRAINING LOGIC
        close = np.array(res['close'])
        low = np.array(res['low'])
        
        dist_50 = ((close - np.array(res['sma_50'])) / close) * 100.0
        rsi_norm = np.array(res['rsi_14']) / 100.0
        vol_ratio = (np.array(res['atr_14']) / close) * 1000.0

        X = np.column_stack([dist_50, rsi_norm, vol_ratio])
        X = np.nan_to_num(X)

        y = np.zeros(len(close))
        window = 12 
        for i in range(window, len(close) - window):
            current_low = low[i]
            local_min = np.min(low[i-window : i+window+1])
            future_price = close[i+12]
            required_bounce = 1.5 * np.array(res['atr_14'])[i]
            
            if (current_low == local_min) and (future_price > current_low + required_bounce):
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def optimize(self, start_ms, end_ms):
        print(f"Optimizing Thresholds for {self.symbol}...")
        
        current_after = start_ms
        all_probs = []
        all_y_true = []
        
        # 1. Collect all predictions first
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y = self.prepare_features(res)
            if len(X) > 0:
                probs = self.model.predict_proba(X)
                # Get prob of Class 1 (Bottom)
                idx_bottom = list(self.model.classes_).index(1)
                
                all_probs.extend(probs[:, idx_bottom])
                all_y_true.extend(y)
            
            current_after = res['time'][-1]
            
        all_probs = np.array(all_probs)
        all_y_true = np.array(all_y_true)

        print("\n" + "="*50)
        print(f"{'THRESHOLD':<10} | {'SIGNALS':<10} | {'PRECISION':<10} | {'WINNER COUNT':<10}")
        print("="*50)

        # 2. Test Thresholds
        for t in [0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.98, 0.99]:
            y_pred = (all_probs > t).astype(int)
            
            # Calculate stats
            signals = np.sum(y_pred)
            if signals > 0:
                prec = precision_score(all_y_true, y_pred, pos_label=1, zero_division=0)
                # Count actual wins
                cm = confusion_matrix(all_y_true, y_pred)
                winners = cm[1][1] if len(cm) > 1 else 0
                
                print(f"{t:<10.2f} | {signals:<10} | {prec:<10.2%} | {winners:<10}")
            else:
                print(f"{t:<10.2f} | 0          | 0.00%      | 0")

optimizer = BpMarketsOptimizer("EUR-USD", "1h")
optimizer.optimize(start_ms=1420070400000, end_ms=1768880340000)