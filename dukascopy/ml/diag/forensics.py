import torch
import torch.nn as nn
import os
import pandas as pd
import polars as pl
import numpy as np
import math
from typing import List, Dict, Any
from datetime import datetime, timezone
from util.api import get_data

NUMBER_DECIMALS = 10

# ==========================================
# Neural Network Architecture
# ==========================================
class SingularityInference(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int):
        super(SingularityInference, self).__init__()
        self.l1 = nn.Linear(input_dim, hidden_dim)
        self.l2 = nn.Linear(hidden_dim, 1)
        self.activation = nn.GELU() 
        self.out_act = nn.Sigmoid()
        
    def forward(self, x):
        h1 = self.l1(x)
        a1 = self.activation(h1)
        s2 = self.l2(a1)
        return self.out_act(s2), h1, a1, s2

# ==========================================
# Forensic Stepper Core
# ==========================================
class ForensicWalkForward:
    def __init__(self, center: str, model_path: str, symbol: str, timeframe: str, start_ms: int, star_score=0.20, options: Dict = None):
        self.center = center
        self.model_path = model_path
        self.model_name = os.path.basename(model_path)
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_ms = start_ms
        self.options = options if options else {}
        self.targets = None

        self.total_bars = 0
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self._load_targets()
        self._load_checkpoint()
        self.base_indicators = self._extract_indicators()

        self.star_score = star_score
        self.score_window = []
        self.ma_period = 2
        self.last_ma = 0.0

    def _load_targets(self):
        print(f"🔍 [Forensic Stepper]: loading targets '{self.center}'...")
        center_df = get_data(
            self.symbol, 
            self.timeframe, 
            after_ms=self.start_ms, 
            limit=1000000, # load them all
            order="asc", 
            indicators=[self.center], 
            options={**self.options, "return_polars": True} 
        )
        self.total_bars = len(center_df)
        target_times = center_df.filter(pl.col(self.center) != 0)["time_ms"].to_list()
        self.targets = set(target_times)
        print(f"🎯 [Forensic Stepper]: Extracted {len(self.targets)} confirmed target zones.")
                
    def _load_checkpoint(self):
        print(f"🔍 [Forensic Stepper]: Interrogating checkpoint '{self.model_name}'...")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")
            
        checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=False)
        self.active_features = checkpoint.get('feature_names', [])
        self.threshold = float(checkpoint.get('threshold', 0.2433))
        
        self.means = checkpoint['means'].to(self.device)
        self.stds = checkpoint['stds'].to(self.device)
        
        w1 = checkpoint['W1'].to(self.device)
        b1 = checkpoint['B1'].to(self.device).reshape(-1)
        w2 = checkpoint['W2'].to(self.device)
        b2 = checkpoint['B2'].to(self.device).reshape(-1)
        
        in_dim, hid_dim = w1.shape
        self.model = SingularityInference(input_dim=in_dim, hidden_dim=hid_dim).to(self.device)
        self.model.l1.weight.data = w1.t()
        self.model.l1.bias.data = b1
        
        final_w2 = w2 if w2.shape[0] == 1 else w2.t()
        self.model.l2.weight.data = final_w2
        self.model.l2.bias.data = b2
        
        self.model.eval()

    def _extract_indicators(self) -> List[str]:
        """
        Splits feature names by '__' and extracts the unique base indicator strings.
        """
        unique_indicators = set()
        
        for feature in self.active_features:
            base_name = feature.split(':')[0].split('__')[0]
            unique_indicators.add(base_name)
            
        unique_indicators.add("is-open")
            
        return list(unique_indicators)

    def _run_inference(self, raw_df: pl.DataFrame) -> float:
        """
        Runs the neural net specifically on the final candle to guarantee
        zero look-ahead bias on the current step, utilizing EXACT production ordering.
        """
        pdf = raw_df.to_pandas()
        
        if 'is-open' in pdf.columns:
            inference_df = pdf[pdf['is-open'] == 0].copy()
        else:
            inference_df = pdf.copy()
            
        if inference_df.empty:
            return 0.0
            
        inference_df = inference_df.tail(1)

        ordered_columns = []
        for f in self.active_features:
            if f in inference_df.columns:
                ordered_columns.append(inference_df[f].fillna(0.0).values)
            else:
                ordered_columns.append(np.zeros(len(inference_df)))

        raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)
        raw_model_tensor = torch.from_numpy(raw_values).to(self.device)

        with torch.no_grad():
            normalized_tensor = (raw_model_tensor - self.means) / (self.stds + 1e-8)
            
            out, h1, a1, s2 = self.model(normalized_tensor)
            predictions = out.squeeze().cpu().numpy()
            
            if predictions.ndim == 0:
                predictions = np.array([predictions.item()])
                
        return float(predictions[-1])

    def execute_walk(self, max_steps: int) -> pd.DataFrame:
        print(f"🚀 [Forensic Stepper]: Initiating Walk-Forward for {max_steps} steps.")
        print(f"📦 Payload Indicators: {self.base_indicators}")
        print("-" * 60)
        
        walk_results = []
        num_steps = max_steps if max_steps > 0 else self.total_bars
        
        for step in range(1, num_steps + 1):
            current_limit = step
            
            raw_df = get_data(
                self.symbol, 
                self.timeframe, 
                after_ms=self.start_ms, 
                limit=current_limit, 
                order="asc", 
                indicators=self.base_indicators, 
                options={**self.options, "return_polars": True} 
            )
            
            if raw_df is None or len(raw_df) == 0:
                print(f"⚠️ Step {step}: No data returned.")
                continue

            latest_score = self._run_inference(raw_df)
            latest_signal = 1.0 if latest_score > self.threshold else 0.0
            
            latest_state = raw_df.tail(1).to_dicts()[0]
            latest_state["ml_score"] = latest_score
            latest_state["ml_signal"] = latest_signal

            is_center_signal = latest_state["time_ms"] in self.targets
            latest_state["is_target"] = is_center_signal
            
            walk_results.append(latest_state)

            precision = NUMBER_DECIMALS

            # --- MAGNITUDE WAVE LOGIC ---
            latest_len = max(0, len(f"{latest_score:>.10f}".split('.')[1].lstrip('0'))-4)

            self.score_window.append(latest_len)
            if len(self.score_window) > self.ma_period:
                self.score_window.pop(0)
                
            current_ma = math.ceil(sum(self.score_window) / len(self.score_window))
            
            stars = ""
            if current_ma > 0:
                char = "*" if current_ma >= self.last_ma else "."
                stars = char * current_ma
                
            self.last_ma = current_ma
            
            target_str = ""
            if is_center_signal:
                target_str = " HIT" if len(stars)>0 else " MISS"

            print(f"Step {step:>4}/{num_steps} | Bars: {len(raw_df):>4} | "
                  f"Time: {latest_state.get('time_ms')} | "
                  f"Score: {latest_score:>.{precision}f} | "
                  f"Target: {int(is_center_signal)} | {stars:<6}{target_str}")
            
        print("-" * 60)
        print("✅ [Forensic Stepper]: Walk-Forward Complete.")
        
        return pd.DataFrame(walk_results)


if __name__ == "__main__":
    dt_str = "2026-01-01"
    epoch_ms = int(datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    stepper = ForensicWalkForward(
        center="example-pivot-finder_10_bottoms",  # We use 10 since that is a better match
        model_path="checkpoints/model-best-gen13-f1-0.6316.pt",
        symbol="GBP-USD",
        timeframe="4h",
        start_ms=epoch_ms,
        star_score=0.00000005, 
        options={"use_cache": False}
    )
    
    # Run the simulation 
    # NOTE: Set max_steps to e.g. 50 to test it quickly before executing a full -1 run
    history_df = stepper.execute_walk(max_steps=-1)