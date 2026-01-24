import requests, json, numpy as np, joblib, os, pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timezone, timedelta

class BpMarketsTrainer:
    def __init__(self, symbol="EUR-USD", timeframe="1d", save_path="../models"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        # Full indicator suite required for the 12-feature regime model
        self.indicators = "atr(14):sma(50):rsi(14):bbands(20,2):macd(12,26,9):cci(20):adx(14):stoch(14,3,3)"
        self.save_path = save_path 
        
        self.model = RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            class_weight='balanced_subsample',
            random_state=42,
            n_jobs=-1 
        )

    def get_data(self, after_ms, until_ms):
        url = f"{self.base_url}{self.symbol}%2C{self.tf}%5B{self.indicators}%5D/after/{after_ms}/until/{until_ms}/output/JSON"
        try:
            response = requests.get(url, params={"limit": 20000, "subformat": 3, "order": "asc"})
            data = json.loads(response.text)
            return pd.DataFrame(data['result'])
        except Exception as e:
            print(f"Data Fetch Error for {self.symbol}: {e}")
            return None

    def prepare_features(self, df):
        # 1. MOMENTUM / OVERSOLD
        df['rsi_norm'] = df['rsi_14'] / 100.0
        stoch_key = 'stoch_14_3_3__k' if 'stoch_14_3_3__k' in df else 'rsi_14' 
        df['stoch_k'] = df[stoch_key] / 100.0
        
        # MACD Histogram Z-Score (Scale Invariance)
        hist = df['macd_12_26_9__hist']
        df['macd_hist_z'] = (hist - hist.rolling(50).mean()) / hist.rolling(50).std()
        
        # 2. VOLATILITY
        df['vol_ratio'] = df['atr_14'] / df['close']
        df['bb_width'] = (df['bbands_20_2__upper'] - df['bbands_20_2__lower']) / df['bbands_20_2__mid']

        # 3. PRICE STRUCTURE
        df['dist_sma50'] = (df['close'] - df['sma_50']) / df['close']
        df['body_strength'] = (df['close'] - df['open']) / df['atr_14'].replace(0, 0.001)
        
        total_range = (df['high'] - df['low']).replace(0, 0.001)
        # Relative Height: Midpoint of body relative to candle range
        body_mid = (df['open'] + df['close']) / 2
        df['rel_height'] = (body_mid - df['low']) / total_range

        # 4. TREND / RELATIVE
        df['adx_norm'] = df['adx_14__adx'] / 100.0
        df['cci_norm'] = df['cci_20__cci'] / 200.0

        # 5. TIME-BASED (Cyclical)
        df['time_dt'] = pd.to_datetime(df['time'], unit='ms')
        df['day_sin'] = np.sin(2 * np.pi * df['time_dt'].dt.dayofweek / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['time_dt'].dt.dayofweek / 7)

        features = [
            'rsi_norm', 'stoch_k', 'macd_hist_z', 'vol_ratio', 'bb_width',
            'dist_sma50', 'body_strength', 'rel_height', 'adx_norm', 'cci_norm',
            'day_sin', 'day_cos'
        ]
        
        X = df[features].fillna(0).values

        # 6. TRIPLE BARRIER LABELING
        y = np.zeros(len(df))
        close, low, atr = df['close'].values, df['low'].values, df['atr_14'].values
        
        for i in range(10, len(df) - 20):
            # Only label if it's a 10-day local low
            if low[i] == np.min(low[i-10:i+1]):
                target = close[i] + (3.0 * atr[i]) # 3:1 Reward
                stop = close[i] - (1.0 * atr[i])   # 1:1 Risk
                
                for j in range(i + 1, i + 20): 
                    if close[j] >= target:
                        y[i] = 1 
                        break
                    if close[j] <= stop:
                        y[i] = 0 
                        break
        return X, y

    def train_loop(self, start_ms, end_ms):
        print(f"--- Processing {self.symbol} ---")
        df = self.get_data(start_ms, end_ms)
        if df is None or df.empty: return
            
        X, y = self.prepare_features(df)
        X_train, y_train = X[:-20], y[:-20]
        
        print(f"Training Samples: {len(y_train)} | High-Quality Bottoms: {int(np.sum(y_train))}")
        self.model.fit(X_train, y_train)
        
        os.makedirs(self.save_path, exist_ok=True)
        filename = f"{self.symbol}-{self.tf}-regime-engine.pkl"
        joblib.dump(self.model, os.path.join(self.save_path, filename))
        print(f"SAVED: {filename}\n")

# RUN TRAINER
assets = ['EUR-USD', 'GBP-USD', 'USD-CAD', 'USD-JPY', 'AUD-USD']
after_ms = int(datetime.strptime("2018-01-01", "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
until_ms = int((datetime.now(timezone.utc) - timedelta(days=100)).timestamp() * 1000)
save_dir = Path(__file__).resolve().parent.parent / "models"

for asset in assets:
    trainer = BpMarketsTrainer(asset, "1d", save_dir)
    trainer.train_loop(start_ms=after_ms, end_ms=until_ms)