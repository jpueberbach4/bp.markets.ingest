import requests, json, numpy as np, joblib, os, pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timezone, timedelta

class BpMarketsTrainer:
    def __init__(self, symbol="GBP-USD", timeframe="1d", save_path="../models"):
        self.base_url = "http://localhost:8000/ohlcv/1.1/select/"
        self.symbol, self.tf = symbol, timeframe
        
        # CHANGED: Switched to RSI(7) for faster reaction to V-bottoms
        # Indicators: ATR(14) for volatility, SMA(50) for trend, RSI(7) for fast trigger
        self.indicators = "atr(14):sma(50):rsi(7)"
        self.save_path = save_path 
        
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,          # Slightly deeper to learn the specific V-shape patterns
            min_samples_leaf=5,
            class_weight='balanced',
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
            print(f"Data Fetch Error: {e}")
            return None

    def prepare_features(self, df):
        """
        LOGIC REPAIR FOR 2024 RED SQUARES:
        1. Uses RSI(7) instead of 14 for speed.
        2. Detects 'Crush' via Volatility (ATR), not candle color streaks.
        3. Catches 'Falling Knives' (RSI < 20) and 'V-Shapes' (Panic -> Bounce).
        """
        # --- FEATURE ENGINEERING (The 4-Feature Stack) ---
        # Feature 1: Trend Deviation
        df['trend_dev'] = (df['close'] - df['sma_50']) / df['close']
        
        # Feature 2: Normalized RSI (Using RSI 7 now)
        df['rsi_norm'] = df['rsi_7'] / 100.0
        
        # Feature 3: Volatility Ratio
        df['vol_ratio'] = df['atr_14'] / df['close']
        
        # Feature 4: Body Strength
        df['body_strength'] = (df['close'] - df['open']) / df['atr_14'].replace(0, 0.001)

        features = ['trend_dev', 'rsi_norm', 'vol_ratio', 'body_strength']
        X = df[features].fillna(0).values

        # --- LABELING LOGIC (Targeting Apr/Jun/Aug/Sep 2024) ---
        y = np.zeros(len(df))
        
        # Extract numpy arrays for speed
        open_p = df['open'].values
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        atr = df['atr_14'].values
        sma = df['sma_50'].values
        rsi = df['rsi_7'].values
        
        # Window for volatility context
        window = 20 
        
        for i in range(window, len(df) - 15):
            
            # 1. THE SETUP: Volatility Crush
            # Instead of counting red candles (which missed 2024-06-26 due to a doji),
            # we check if price crashed > 2.0x ATR from the recent 5-day high.
            recent_high = np.max(high[i-5:i])
            drop_magnitude = recent_high - low[i]
            is_crush = drop_magnitude > (2.0 * atr[i])
            
            # 2. THE TRIGGER: Panic or V-Shape
            
            # A. Extreme Panic (Catches 2024-04-22 Falling Knife)
            # RSI(7) drops below 20. Immediate signal.
            is_extreme = rsi[i] < 20
            
            # B. V-Shape Bounce (Catches 2024-06-26 and 2024-08-07)
            # RSI was in Panic (< 30) yesterday, and today is a Green Candle
            rsi_was_panic = rsi[i-1] < 30
            is_green_candle = close[i] > open_p[i]
            is_v_shape = rsi_was_panic and is_green_candle
            
            # 3. THE CONTEXT: Exhaustion
            # Price must be below SMA50 (Trend is down/exhausted)
            is_below_sma = close[i] < sma[i]

            # COMBINE
            if is_crush and (is_extreme or is_v_shape) and is_below_sma:
                
                # 4. VERIFICATION: Did it actually bottom?
                # Price must move up at least 1.0x ATR in the next 10 days
                future_max = np.max(close[i+1 : i+11])
                if (future_max - close[i]) >= (1.0 * atr[i]):
                    y[i] = 1 
        
        return X, y

    def train_loop(self, start_ms, end_ms):
        print(f"--- Training 2024-Tuned Sniper: {self.symbol} ---")
        df = self.get_data(start_ms, end_ms)
        if df is None or df.empty: return
            
        X, y = self.prepare_features(df)
        X_train, y_train = X[:-20], y[:-20]
        
        print(f"Total Samples: {len(y_train)} | Targeted Bottoms Found: {int(np.sum(y_train))}")
        self.model.fit(X_train, y_train)
        
        os.makedirs(self.save_path, exist_ok=True)
        # Naming it abottom-engine to match your requested file context if needed
        filename = f"{self.symbol}-engine.pkl" 
        joblib.dump(self.model, os.path.join(self.save_path, filename))
        print(f"SAVED: {filename}\n")


# RUN TRAINER
assets = ['EUR-USD', 'GBP-USD', 'USD-CAD', 'USD-JPY', 'AUD-USD']
after_ms = int(datetime.strptime("2020-01-01", "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
until_ms = int((datetime.now(timezone.utc) - timedelta(days=60)).timestamp() * 1000)
save_dir = Path(__file__).resolve().parent.parent / "models"

for asset in assets:
    trainer = BpMarketsTrainer(asset, "1d", save_dir)
    trainer.train_loop(start_ms=after_ms, end_ms=until_ms)