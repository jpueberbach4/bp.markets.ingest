import requests, json, numpy as np, joblib, os
from sklearn.metrics import precision_score, confusion_matrix

class BpMarketsOptimizer:
    def __init__(self, symbol="EUR-USD", timeframe="1h"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        
        # 1. Load the Random Forest Model
        # We try the 'rf' engine first
        self.model_path = os.path.join(os.getcwd(), f"{self.symbol}-engine.pkl")
        if not os.path.exists(self.model_path):
             self.model_path = os.path.join(os.getcwd(), f"{self.symbol}-engine.pkl")
        
        if os.path.exists(self.model_path):
            print(f"Optimizing Model: {self.model_path}")
            self.model = joblib.load(self.model_path)
        else:
            raise FileNotFoundError("No .pkl model found. Run mltrain.py first.")

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
        
        # --- ZERO-BIAS FEATURES (Must match your trainer) ---
        dist_50 = ((close - np.array(res['sma_50'])) / close) * 100.0
        rsi_norm = np.array(res['rsi_14']) / 100.0
        vol_ratio = (np.array(res['atr_14']) / close) * 1000.0

        X = np.column_stack([dist_50, rsi_norm, vol_ratio])
        X = np.nan_to_num(X)

        y = np.zeros(len(close))
        window = 12 
        
        # Recreate the labels to check accuracy
        for i in range(window, len(close) - window):
            current_low = low[i]
            local_min = np.min(low[i-window : i+window+1])
            is_absolute_low = (current_low == local_min)
            
            future_price = close[i+12]
            required_bounce = 1.0 * np.array(res['atr_14'])[i]
            did_bounce = future_price > (current_low + required_bounce)
            
            if is_absolute_low and did_bounce:
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def optimize(self, start_ms, end_ms):
        current_after = start_ms
        all_probs = []
        all_y_true = []
        
        # 1. Collect all predictions
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y = self.prepare_features(res)
            if len(X) > 0:
                # Get probability of Class 1 (Bottom)
                probs = self.model.predict_proba(X)
                class_map = {c: i for i, c in enumerate(self.model.classes_)}
                idx_bottom = class_map.get(1)
                
                if idx_bottom is not None:
                    all_probs.extend(probs[:, idx_bottom])
                    all_y_true.extend(y)
            
            current_after = res['time'][-1]
            
        all_probs = np.array(all_probs)
        all_y_true = np.array(all_y_true)

        print("\n" + "="*60)
        print(f"{'CONFIDENCE':<12} | {'SIGNALS':<10} | {'PRECISION':<10} | {'WINNERS':<10} | {'FALSE POS':<10}")
        print("="*60)

        # 2. Test High Thresholds
        # Random Forests with balanced weights often need > 0.80
        for t in [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
            y_pred = (all_probs > t).astype(int)
            
            signals = np.sum(y_pred)
            if signals > 0:
                prec = precision_score(all_y_true, y_pred, pos_label=1, zero_division=0)
                cm = confusion_matrix(all_y_true, y_pred)
                # Handle matrix shape differences
                if cm.shape == (2, 2):
                    winners = cm[1][1]
                    false_pos = cm[0][1]
                else:
                    winners = 0
                    false_pos = 0
                
                print(f"> {t:<10.2f} | {signals:<10} | {prec:<10.2%} | {winners:<10} | {false_pos:<10}")
            else:
                print(f"> {t:<10.2f} | 0          | 0.00%      | 0          | 0")

optimizer = BpMarketsOptimizer("EUR-USD", "1h")
optimizer.optimize(start_ms=1420070400000, end_ms=1768880340000)