import yaml
import fnmatch
import pandas as pd
import numpy as np
import torch

from util.api import get_data
from ml.space.space import Universe, Comet, Normalizer
from ml.space.normalizers.factory import NormalizerFactory
from ml.space.comets.factory import CometFactory
from typing import Tuple, Dict, Any
from datetime import datetime


class MilkyWay(Universe):
    def __init__(self, config):
        self.config = config
        
        self.symbol = None
        self.timeframe = None
        self.after_ms = None
        self.until_ms = None
        self.limit = 1000000

        self._feature_table = None
        self._target_series = None
        self._feature_names = []
        self._discarded_dimensions = [] # Track string-polluted columns
        self._comets: Dict[str, Comet] = {}
        self._normalizers: Dict[str, Normalizer] = {}
        
        self.features_to_request, self.filter_patterns, self.target_col = self._load_config()

    def _load_config(self):
        try:    
            # read symbol and timeframe from config
            self.symbol, self.timeframe = self.config.get('fabric').get('matter').split('/',1)
            
            # extract the other fabrics
            self.after_ms = int(datetime.fromisoformat(str(self.config.get('fabric').get('after'))).timestamp() * 1000)
            self.until_ms = int(datetime.fromisoformat(str(self.config.get('fabric').get('until'))).timestamp() * 1000)

            print(f"🌌 [Space]: Materializing MilkyWay for {self.symbol}... {self.after_ms} -> {self.until_ms}")

            # Initialize the Comets
            for comet_name in self.config.get('comets'):
                self._comets[comet_name] = CometFactory.manifest(comet_name)

            # Initialize the Normalizers
            for normalizer_name in self.config.get('normalizers').keys():
                normalizer_config = self.config.get('normalizers').get(normalizer_name)
                is_disabled = str(normalizer_config.get('disabled', 'false')).strip().lower() in ('true', '1', 't', 'y', 'yes')

                if is_disabled:
                    continue
                self._normalizers[normalizer_name] = NormalizerFactory.manifest(normalizer_name, normalizer_config)
       
            center = self.config.get('center', [])
            target = center[0] if isinstance(center, list) and len(center) > 0 else None
            
            features = self.config.get('features', [])
            if target and target not in features:
                features.append(target)
                
            return features, self.config.get('filter', []), target
        except Exception as e:
            print(f"❌ [MilkyWay Init Error]: {e}")
            raise

    def ignite(self, after_ms=1546300800000, until_ms=2757952000000, limit=10000, options=None):
        if options is None:
            options = {}

        print(f"🌌 [Space]: Igniting MilkyWay for {self.symbol}...")

        raw_polars = get_data(
            symbol=self.symbol,
            timeframe=self.timeframe,
            after_ms=self.after_ms,
            until_ms=self.until_ms,
            limit=self.limit,
            order="asc",
            indicators=self.features_to_request,
            options={**options, "return_polars": True}
        )
        
        df = raw_polars.to_pandas()

        max_time_date = pd.to_datetime(df['time_ms'].max(), unit='ms').strftime('%Y-%m-%d')
        print(f"🌌 [Space]: Temporal boundary detected at {max_time_date}. Beyond this, there is only the future.")

        # --- Handle Target ---
        if self.target_col in df.columns:
            raw_target = df[self.target_col].copy()
            # Ensure target itself is numeric before calculation
            if not pd.api.types.is_numeric_dtype(raw_target):
                 raw_target = pd.to_numeric(raw_target, errors='coerce').fillna(0)

            pos_count = (raw_target == 1).sum()
            neg_count = (raw_target == -1).sum()
            
            print(f"📊 [Data Audit]: target_col: {self.target_col}")
            print(f"📊 [Data Audit]: Total Bars: {len(df)}")
            print(f"📊 [Data Audit]: Signals found: {pos_count + neg_count}")
            
            self._target_series = (raw_target != 0).astype(np.float32)
            self._target_series.name = "target"
        else:
            print(f"⚠️ [Space Error]: Target column '{self.target_col}' not found!")
            self._target_series = pd.Series(np.zeros(len(df)), name="target")

        # --- Filter Patterns & Metadata ---
        cols_to_drop = []
        for pattern in self.filter_patterns:
            matches = fnmatch.filter(df.columns, pattern)
            cols_to_drop.extend(matches)
        
        metadata = ['time_ms', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'timeframe']
        final_drops = list(set(cols_to_drop + [c for c in metadata if c in df.columns]))
        
        if self.target_col in df.columns and self.target_col not in final_drops:
            final_drops.append(self.target_col)

        work_df = df.drop(columns=[c for c in final_drops if c in df.columns])

        # --- FIX: volatility data is not much, causes nan at the beginning, however, rest of column is fine ---
        work_df = work_df.bfill().ffill().fillna(0)

        # --- NEW: Filter out "Atmospheric Waste" (Non-numeric columns) ---
        numeric_df = work_df.select_dtypes(include=[np.number])
        self._discarded_dimensions = [c for c in work_df.columns if c not in numeric_df.columns]
        
        self._feature_table = numeric_df
        self._feature_names = self._feature_table.columns.tolist()

        if self._discarded_dimensions:
            print(f"🧹 [Space]: Radiated {len(self._discarded_dimensions)} string-polluted dimensions.")

        print(f"✅ [Space]: Discovered {len(self._feature_names)} valid dimensions.")

    def bigbang(self) -> Tuple[pd.DataFrame, pd.Series]:
        if self._feature_table is None:
            raise RuntimeError("Cannot Big Bang an unignited universe. Call ignite() first.")
        
        print("🔭 [Space]: Applying Cosmic Normalization (Redshift & Kinematics)...")
        
        current_names = list(self._feature_table.columns)
        normalized_tensor = torch.tensor(self._feature_table.values, dtype=torch.float32)

        for normalizer in self._normalizers.values():
            if hasattr(normalizer, 'generate_names'):
                current_names = normalizer.generate_names(current_names)
            
            # Execute the transformation (Direction, Velocity, Presence blocks)
            normalized_tensor = normalizer.forward(normalized_tensor)
        
        self._feature_names = current_names

        self._feature_table = pd.DataFrame(
            normalized_tensor.cpu().numpy(), # .cpu() ensures we can move from CUDA to RAM
            columns=self._feature_names, 
            index=self._feature_table.index
        )

        self.audit()
        
        print(f"💥 [Space]: Big Bang Successful! {len(self._feature_names)} dimensions normalized.")
        return self._feature_table, self._target_series

    def dimensions(self):
        return self._feature_table.shape if self._feature_table is not None else (0,0)

    def features(self):
        return self._feature_names

    def eject(self, filename: str, data: Any, is_model: bool = False, is_gene_dump: bool = False):
        for comet in self._comets.values():
            comet.deposit(filename, data, is_model, is_gene_dump)

    def audit(self):
        """
        Dumps a statistical report of NaNs and string-polluted columns.
        """
        if self._feature_table is None:
            print("❌ [Spectrograph]: No matter found. Ignite the universe first.")
            return

        print("\n🔬 [Spectrograph]: Dimension Audit Report")
        print("=" * 60)
        
        # Report String Voids (Dropped Columns)
        if self._discarded_dimensions:
            print(f"🚫 [Atmospheric Waste]: {len(self._discarded_dimensions)} dimensions dropped (Non-Numeric/Strings)")
            for col in self._discarded_dimensions:
                print(f"   - {col}")
            print("-" * 60)
        else:
            print("✅ No string pollution detected in requested features.")

        # Report NaN Voids (Existing Columns)
        nan_counts = self._feature_table.isna().sum()
        nan_percentages = (nan_counts / len(self._feature_table)) * 100
        
        void_report = pd.DataFrame({
            'void_count': nan_counts,
            'void_percent': nan_percentages
        }).query('void_count > 0').sort_values(by='void_count', ascending=False)

        if void_report.empty:
            print(f"💎 Matter Check: All {len(self._feature_names)} dimensions are solid (0 NaNs).")
        else:
            print(f"⚠️ [Void Report]: {len(void_report)} dimensions contain NaNs")
            print(void_report.to_string())
            
            critical = void_report[void_report['void_percent'] > 50]
            if not critical.empty:
                print(f"🚨 CRITICAL: {len(critical)} columns are more than 50% empty!")

        print("=" * 60)
        return void_report