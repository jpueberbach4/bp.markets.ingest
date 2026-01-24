import pandas as pd, numpy as np, joblib, os
from pathlib import Path
from typing import Dict, Any, List

_ENGINE_CACHE = {}

def description() -> str:
    return "ML Sniper: 12-Feature Regime Bottoms (Validated)"

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 305.0, "verified": 1, "panel": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "model_path": args[0] if len(args) > 0 else "{symbol}-{timeframe}-regime-engine.pkl",
        "threshold": args[1] if len(args) > 1 else "0.59"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    from util.api import get_data
    
    # 1. SETUP & FETCH
    row = df.iloc[0]

    symbol, timeframe = row.symbol, row.timeframe
    after_ms, until_ms = int(row.sort_key), int(df.iloc[-1].sort_key)
    
    indicators = ['atr_14', 'sma_50', 'rsi_14', 'bbands_20_2', 'macd_12_26_9', 'cci_20', 'adx_14', 'stoch_14_3_3']
    df_ext = get_data(symbol, timeframe, after_ms, until_ms+1, len(df), "asc", indicators, {"disable_recursive_mapping": True})

    if df_ext is None or df_ext.empty:
        return pd.DataFrame({'confidence': 0, 'signal': 0}, index=df.index)

    # 2. LOAD MODEL
    model_name = options.get('model_path', f"{symbol}-{timeframe}-regime-engine.pkl")
    threshold = float(options.get('threshold', '0.59'))
    path = os.path.join(Path(__file__).resolve().parent / "models", model_name)
    
    if path not in _ENGINE_CACHE:
        _ENGINE_CACHE[path] = joblib.load(path) if os.path.exists(path) else None
    
    model = _ENGINE_CACHE[path]
    if not model: return pd.DataFrame({'confidence': 0, 'signal': 0}, index=df.index)

    # 3. FEATURE ENGINEERING (Sync with bottoms.py)
    rsi_norm = df_ext['rsi_14'] / 100.0
    stoch_key = 'stoch_14_3_3__k' if 'stoch_14_3_3__k' in df_ext else 'rsi_14'
    stoch_k = df_ext[stoch_key] / 100.0
    
    hist = df_ext['macd_12_26_9__hist']
    macd_hist_z = (hist - hist.rolling(50).mean()) / hist.rolling(50).std()
    
    vol_ratio = df_ext['atr_14'] / df_ext['close']
    bb_width = (df_ext['bbands_20_2__upper'] - df_ext['bbands_20_2__lower']) / df_ext['bbands_20_2__mid']

    dist_sma50 = (df_ext['close'] - df_ext['sma_50']) / df_ext['close']
    body_strength = (df_ext['close'] - df_ext['open']) / df_ext['atr_14'].replace(0, 0.001)
    
    total_range = (df_ext['high'] - df_ext['low']).replace(0, 0.001)
    body_mid = (df_ext['open'] + df_ext['close']) / 2
    rel_height = (body_mid - df_ext['low']) / total_range

    adx_norm = df_ext['adx_14__adx'] / 100.0
    cci_norm = df_ext['cci_20__cci'] / 200.0

    time_dt = pd.to_datetime(df_ext['sort_key'], unit='ms')
    day_sin, day_cos = np.sin(2*np.pi*time_dt.dt.dayofweek/7), np.cos(2*np.pi*time_dt.dt.dayofweek/7)

    # 4. PREDICT
    X = np.column_stack([
        rsi_norm.fillna(0.5), stoch_k.fillna(0.5), macd_hist_z.fillna(0),
        vol_ratio.fillna(0), bb_width.fillna(0), dist_sma50.fillna(0),
        body_strength.fillna(0), rel_height.fillna(0), # SYNCED
        adx_norm.fillna(0.2), cci_norm.fillna(0), day_sin, day_cos
    ])
    
    probs = model.predict_proba(X)
    idx_bottom = {c: i for i, c in enumerate(model.classes_)}.get(1)
    confidence = probs[:, idx_bottom] if idx_bottom is not None else np.zeros(len(df_ext))

    # 1. Create a results dataframe from the external data
    raw_results = pd.DataFrame({
        'sort_key': df_ext['sort_key'],
        'confidence': confidence,
        'signal': np.where(confidence >= threshold, 1, 0)
    })

    # 2. Map these results back to the original 'df' using sort_key
    # This ensures every confidence value matches the correct timestamp
    final_df = df[['sort_key']].merge(raw_results, on='sort_key', how='left')

    # 3. Return with the original index preserved
    return final_df[['confidence', 'signal']].set_index(df.index).fillna(0)