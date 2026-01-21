import requests, json, numpy as np, joblib, os
from sklearn.metrics import classification_report, confusion_matrix, precision_score

class BpMarketsEvaluator:
    def __init__(self, symbol="EUR-USD", timeframe="1h"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        self.indicators = "atr(14):sma(50):rsi(14)"
        
        # Load the trained model
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
        # EXACT MATCH to mltrain.py (Zero-Bias Logic)
        close = np.array(res['close'])
        low = np.array(res['low'])
        
        # 1. Features
        dist_50 = ((close - np.array(res['sma_50'])) / close) * 100.0
        rsi_norm = np.array(res['rsi_14']) / 100.0
        vol_ratio = (np.array(res['atr_14']) / close) * 1000.0

        X = np.column_stack([dist_50, rsi_norm, vol_ratio])
        X = np.nan_to_num(X)

        # 2. Labels (Ground Truth)
        y = np.zeros(len(close))
        window = 12 
        
        for i in range(window, len(close) - window):
            current_low = low[i]
            local_min = np.min(low[i-window : i+window+1])
            is_absolute_low = (current_low == local_min)
            
            future_price = close[i+12]
            required_bounce = 1.5 * np.array(res['atr_14'])[i]
            did_bounce = future_price > (current_low + required_bounce)
            
            if is_absolute_low and did_bounce:
                y[i] = 1 # True Bottom
        
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
                # Predict using the loaded model
                # We use probability threshold > 0.60 just like the indicator
                probs = self.model.predict_proba(X)
                class_map = {c: i for i, c in enumerate(self.model.classes_)}
                idx_bottom = class_map.get(1)
                
                if idx_bottom is not None:
                    confidence = probs[:, idx_bottom]
                    y_pred = (confidence > 0.60).astype(int)
                    
                    y_true_all.extend(y_true)
                    y_pred_all.extend(y_pred)
            
            current_after = res['time'][-1]
            # print(f"Processed batch ending: {current_after}")

        # --- FINAL REPORT ---
        print("\n" + "="*40)
        print("     SNIPER MODEL EVALUATION REPORT     ")
        print("="*40)
        
        # 1. Confusion Matrix
        cm = confusion_matrix(y_true_all, y_pred_all)
        print(f"\n[CONFUSION MATRIX]")
        print(f"True Negatives (Correctly Ignored): {cm[0][0]}")
        print(f"False Positives (Fake Signals):     {cm[0][1]}  <-- WE WANT THIS LOW")
        print(f"False Negatives (Missed Bottoms):   {cm[1][0]}")
        print(f"True Positives (Sniper Hits):       {cm[1][1]}  <-- WE WANT THIS HIGH")
        
        # 2. Precision (The most important stat)
        precision = precision_score(y_true_all, y_pred_all, pos_label=1)
        print(f"\n[SNIPER ACCURACY]")
        print(f"Precision: {precision:.2%}")
        print("(This means: When the AI says 'Buy', it is right X% of the time)")

        # 3. Full Report
        print("\n[DETAILED METRICS]")
        print(classification_report(y_true_all, y_pred_all, target_names=['Noise', 'Bottom']))

# Run Evaluation (Same period as training to verify learning)
evaluator = BpMarketsEvaluator("EUR-USD", "1h")
evaluator.evaluate(start_ms=1420070400000, end_ms=1768880340000)