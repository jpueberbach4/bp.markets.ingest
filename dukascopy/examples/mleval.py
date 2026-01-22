import requests, json, numpy as np, joblib, os
from sklearn.metrics import classification_report, confusion_matrix, precision_score

class BpMarketsEvaluator:
    def __init__(self, symbol="EUR-USD", timeframe="1h"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        
        self.model_path = os.path.join(os.getcwd(), f"{self.symbol}-engine.pkl")
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            print(f"LOADED: {self.model_path}")
        else:
            raise FileNotFoundError(f"Model not found at {self.model_path}")

    def get_data_chunk(self, after_ms, limit=5000):
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/output/JSONP"
        params = {"limit": limit, "subformat": 3, "order": "asc"}
        try:
            response = requests.get(url, params=params)
            raw_json = response.text.split('(', 1)[1].rsplit(')', 1)[0]
            return json.loads(raw_json)['result']
        except: return None

    def prepare_features(self, res):
        # MUST MATCH mltrain.py EXACTLY (4 FEATURES)
        close = np.array(res['close'])
        open_p = np.array(res['open'])
        low = np.array(res['low'])
        atr = np.array(res['atr_14'])
        
        # 1. Trend
        dist_50 = (close - np.array(res['sma_50'])) / close
        # 2. RSI
        rsi_norm = np.array(res['rsi_14']) / 100.0
        # 3. Volatility
        vol_ratio = atr / close
        # 4. Body Strength (The Missing Feature)
        safe_atr = np.where(atr == 0, 0.00001, atr)
        body_strength = (close - open_p) / safe_atr

        X = np.column_stack([dist_50, rsi_norm, vol_ratio, body_strength])
        X = np.nan_to_num(X)

        # Labels (Ground Truth)
        y = np.zeros(len(close))
        window = 12 
        
        for i in range(window, len(close) - window):
            current_low = low[i]
            local_min = np.min(low[i-window : i+window+1])
            is_absolute_low = (current_low == local_min)
            
            # Match Trainer Bounce logic (0.5 ATR)
            future_price = close[i+12]
            required_bounce = 0.5 * atr[i]
            did_bounce = future_price > (current_low + required_bounce)
            
            if is_absolute_low and did_bounce:
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def evaluate(self, start_ms, end_ms):
        current_after = start_ms
        print(f"Evaluating Model on {self.symbol}...")
        
        y_true_all = []
        y_pred_all = []
        
        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y_true = self.prepare_features(res)
            
            if len(X) > 0:
                # Predict
                probs = self.model.predict_proba(X)
                class_map = {c: i for i, c in enumerate(self.model.classes_)}
                idx_bottom = class_map.get(1)
                
                if idx_bottom is not None:
                    confidence = probs[:, idx_bottom]
                    # Evaluate at 0.65 threshold (Standard Pro setting)
                    y_pred = (confidence > 0.65).astype(int)
                    
                    y_true_all.extend(y_true)
                    y_pred_all.extend(y_pred)
            
            current_after = res['time'][-1]

        print("\n" + "="*40)
        print("     SNIPER MODEL EVALUATION REPORT     ")
        print("="*40)
        
        cm = confusion_matrix(y_true_all, y_pred_all)
        print(f"\n[CONFUSION MATRIX]")
        print(f"True Negatives (Correctly Ignored): {cm[0][0]}")
        print(f"False Positives (Fake Signals):     {cm[0][1]}")
        print(f"False Negatives (Missed Bottoms):   {cm[1][0]}")
        print(f"True Positives (Sniper Hits):       {cm[1][1]}")
        
        precision = precision_score(y_true_all, y_pred_all, pos_label=1)
        print(f"\n[SNIPER ACCURACY]")
        print(f"Precision: {precision:.2%}")

# Run Evaluation
evaluator = BpMarketsEvaluator("GBP-USD", "1d")
evaluator.evaluate(start_ms=1420070400000, end_ms=1768880340000)