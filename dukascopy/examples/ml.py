import requests
import json
import numpy as np
import time
import joblib  # For saving the model
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

class BpMarketsTrainer:
    def __init__(self, symbol="EUR-USD", timeframe="1m"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol = symbol
        self.tf = timeframe
        self.indicators = "atr(14):sma(20):sma(50):rsi(14)"
        self.model = SGDClassifier(loss='log_loss')
        self.scaler = StandardScaler()
        self.window_size = 50

    def get_data_chunk(self, after_ms, limit=5000):
        """Calls API using 'after' and 'asc' order for forward progression"""
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/output/JSONP"
        # order=asc is critical here so the array is [oldest -> newest]
        params = {"limit": limit, "subformat": 3, "order": "asc"}
        
        try:
            response = requests.get(url, params=params)
            raw_json = response.text.split('(', 1)[1].rsplit(')', 1)[0]
            data = json.loads(raw_json)
            return data['result']
        except Exception as e:
            print(f"Fetch error: {e}")
            return None

    def prepare_features(self, res):
        """Prepares stationary features from ascending (forward) data"""
        close = np.array(res['close'])
        rsi = np.array(res['rsi_14'])
        sma20 = np.array(res['sma_20'])
        sma50 = np.array(res['sma_50'])
        
        # Stationary Transformations
        dist_20 = (close - sma20) / close
        dist_50 = (close - sma50) / close
        rsi_scaled = rsi / 100.0
        
        X = np.column_stack([dist_20, dist_50, rsi_scaled])
        
        # TARGET: Predict if price 5 mins in the FUTURE is higher than current Close
        # In 'asc' order, index 10 is 5 minutes AFTER index 5.
        # Shift -5 looks forward in the array.
        y = (np.roll(close, -5) > close).astype(int)
        
        # Remove the last 5 rows because we don't know the future for them yet
        return X[:-5], y[:-5]

    def train_loop(self, start_ms, end_ms):
        current_after = start_ms
        print(f"Starting FORWARD Training: {self.symbol}...")
        
        while current_after < end_ms:
            try:
                res = self.get_data_chunk(current_after)
                
                if not res or len(res['time']) < 100:
                    print("End of data reached or empty chunk.")
                    break
                
                X, y = self.prepare_features(res)
                
                if len(X) > 0:
                    # Incremental learning: model weights move from 2006 -> 2026
                    self.model.partial_fit(X, y, classes=[0, 1])
                
                # Update pointer to the last timestamp in the chunk to move forward
                last_ts = res['time'][-1]
                
                # Safety break to prevent infinite loops if API returns same data
                if last_ts <= current_after:
                    break
                    
                current_after = last_ts
                
                readable_date = time.strftime('%Y-%m-%d', time.gmtime(current_after/1000))
                print(f"Progress: {readable_date}")
                
            except Exception as e:
                print(f"Error at {current_after}: {e}")
                break
        
        # Save the engine once 20 years are processed
        joblib.dump(self.model, f"{self.symbol}_engine.pkl")
        print("Training complete and model saved.")

# --- RUN FORWARD ---
# Start: 2006-01-01 (1136073600000)
# End: Jan 2026 (1768880340000)
trainer = BpMarketsTrainer("EUR-USD","1h")
trainer.train_loop(start_ms=1136073600000, end_ms=1768880340000)