import requests, json, numpy as np, joblib, os
from sklearn.metrics import classification_report, confusion_matrix, precision_score

class BpMarketsTopEvaluator:
    def __init__(self, symbol="GBP-USD", timeframe="1d"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        
        # Load the Top-specific engine
        self.model_path = os.path.join(os.getcwd(), f"{self.symbol}-top-engine.pkl")
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            print(f"LOADED FOR EVALUATION: {self.model_path}")
        else:
            raise FileNotFoundError(f"Top model not found. Run mltrain_top.py first.")

    def get_data_chunk(self, after_ms, limit=5000):
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/output/JSONP"
        params = {"limit": limit, "subformat": 3, "order": "asc"}
        try:
            response = requests.get(url, params=params)
            raw_json = response.text.split('(', 1)[1].rsplit(')', 1)[0]
            return json.loads(raw_json)['result']
        except: return None

    def prepare_features(self, res):
        # Must match Trainer exactly
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

        # Ground Truth Labeling for Tops
        y = np.zeros(len(close))
        window = 12 
        for i in range(window, len(close) - window):
            current_high = high[i]
            local_max = np.max(high[i-window : i+window+1])
            future_price = close[i+12]
            required_drop = 0.5 * atr[i]
            
            if (current_high == local_max) and (future_price < current_high - required_drop):
                y[i] = 1 
        
        return X[window:-window], y[window:-window]

    def run_eval(self, start_ms, end_ms):
        current_after = start_ms
        y_true_all, y_pred_all = [], []
        
        print(f"Testing Top Detector on Out-of-Sample data for {self.symbol}...")

        while current_after < end_ms:
            res = self.get_data_chunk(current_after)
            if not res or len(res['time']) < 100: break
            
            X, y_true = self.prepare_features(res)
            
            if len(X) > 0:
                probs = self.model.predict_proba(X)
                class_map = {c: i for i, c in enumerate(self.model.classes_)}
                idx_top = class_map.get(1)
                
                if idx_top is not None:
                    confidence = probs[:, idx_top]
                    # Use the standard threshold found by the optimizer
                    y_pred = (confidence > 0.65).astype(int)
                    
                    y_true_all.extend(y_true)
                    y_pred_all.extend(y_pred)
            
            current_after = res['time'][-1]

        print("\n" + "="*45)
        print("      AI TOP DETECTOR: PERFORMANCE REPORT     ")
        print("="*45)
        
        cm = confusion_matrix(y_true_all, y_pred_all)
        print(f"\n[STATISTICS]")
        print(f"Correctly Ignored (Noise):    {cm[0][0]}")
        print(f"False Alarms (Fake Tops):     {cm[0][1]}")
        print(f"Missed Peaks:                 {cm[1][0]}")
        print(f"Successful Sniper Hits:       {cm[1][1]}")
        
        prec = precision_score(y_true_all, y_pred_all, zero_division=0)
        print(f"\nFinal Precision (Accuracy):  {prec:.2%}")
        print("-" * 45)
        print("Interpretation: If Precision is > 75%, the model")
        print("is highly reliable for identifying reversals.")

# Evaluate over the last year of data
evaluator = BpMarketsTopEvaluator("GBP-USD", "1d")
evaluator.run_eval(start_ms=1704067200000, end_ms=1768880340000)