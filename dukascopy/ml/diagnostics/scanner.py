"""
===============================================================================
File:        scanner.py
Author:      JP Ueberbach
Created:     2026-03-01

Description:
    Bulk threshold analysis module for MilkyWay neuro-evolved models.

    This module implements a high-performance, vectorized inference scanner
    that evaluates a trained model across a large out-of-sample dataset to:

        - Compute the optimal F1 decision threshold
        - Identify the highest-precision ("Sniper") threshold
        - Analyze precision/recall trade-offs across the full spectrum

    The scanner performs no training and does not mutate model weights.
    It strictly evaluates a frozen checkpoint under real market conditions.

Responsibilities:
    - Load and reconstruct the neural network from checkpoint tensors
    - Fetch and prepare large-scale inference datasets
    - Perform fully vectorized model inference
    - Sweep threshold values from 0.0 to 1.0
    - Report optimal F1 and maximum-precision configurations

Design Notes:
    - Uses GPU automatically if available
    - Normalization mirrors training-time statistics
    - All inference is done in torch.no_grad() mode
    - Gracefully handles edge cases (no data, impossible precision, etc.)
===============================================================================
"""
import torch
import pandas as pd
import polars as pl
import numpy as np
from typing import Dict, List
from util.api import get_data
from ml.diagnostics.base import BaseDiagnostic
from ml.diagnostics.network import SingularityInference


class ThresholdScanner(BaseDiagnostic):
    """
    Performs forensic bulk-inference threshold scanning.

    This diagnostic evaluates model output probabilities over a large
    dataset and determines:

        1. The threshold that maximizes F1 score.
        2. The highest-precision threshold ("Sniper").

    All evaluation is deterministic and read-only.
    """

    def __init__(
        self,
        model_path: str,
        center: str,
        symbol: str,
        timeframe: str,
        start_ms: int,
        options: Dict = None
    ):
        """
        Initializes the ThresholdScanner.

        Args:
            model_path (str): Path to the serialized model checkpoint.
            center (str): Target column used as classification signal.
            symbol (str): Market symbol identifier.
            timeframe (str): Data resolution (e.g., 1d, 4h).
            start_ms (int): Start timestamp in milliseconds.
            options (Dict, optional): Additional API options.
        """
        # Initialize base diagnostic (loads checkpoint + resolves device)
        super().__init__(model_path)

        # Store dataset configuration parameters
        self.center = center
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_ms = start_ms

        # Store optional runtime options (default to empty dict)
        self.options = options if options else {}

        # Extract active feature names from checkpoint
        self.active_features = self.checkpoint.get('feature_names', [])

        # Determine which base indicators must be requested from API
        self.base_indicators = self._extract_indicators()

        # Reconstruct neural network from stored weights
        self._load_network()

    def _extract_indicators(self) -> List[str]:
        """
        Extracts unique base indicator names from feature list.

        Returns:
            List[str]: Unique indicator names required for inference.
        """
        # Start with the classification target indicator
        unique_indicators = set([self.center])

        # Parse each feature to extract its base name
        for feature in self.active_features:
            base_name = feature.split(':')[0].split('__')[0]
            unique_indicators.add(base_name)

        # Always include market open/close state
        unique_indicators.add("is-open")

        # Return list form for API consumption
        return list(unique_indicators)

    def _load_network(self):
        """
        Reconstructs the neural network from checkpoint tensors.

        Returns:
            None
        """
        # Load normalization statistics onto correct device
        self.means = self.checkpoint['means'].to(self.device)
        self.stds = self.checkpoint['stds'].to(self.device)

        # Load first-layer weights and biases
        w1 = self.checkpoint['W1'].to(self.device)
        b1 = self.checkpoint['B1'].to(self.device).reshape(-1)

        # Load second-layer weights and biases
        w2 = self.checkpoint['W2'].to(self.device)
        b2 = self.checkpoint['B2'].to(self.device).reshape(-1)

        # Determine network dimensions from weight shape
        in_dim, hid_dim = w1.shape

        # Instantiate inference model
        self.model = SingularityInference(
            input_dim=in_dim,
            hidden_dim=hid_dim
        ).to(self.device)

        # Assign stored weights (transpose to match PyTorch layout)
        self.model.l1.weight.data = w1.t()
        self.model.l1.bias.data = b1

        # Ensure second layer has correct orientation
        final_w2 = w2 if w2.shape[0] == 1 else w2.t()
        self.model.l2.weight.data = final_w2
        self.model.l2.bias.data = b2

        # Switch model to evaluation mode (disables dropout, etc.)
        self.model.eval()

    def run(self, steps: int = 1000):
        """
        Executes the full threshold scanning procedure.

        Args:
            steps (int): Number of threshold increments between 0 and 1.

        Returns:
            Tuple[float, float]:
                - Sniper threshold
                - Best F1 threshold
        """
        print(f"\n🎯 [Threshold Scanner]: Mapping probability distributions for '{self.model_name}'...")

        # -------------------------------------------------------------
        # 1. Fetch Bulk Market Data
        # -------------------------------------------------------------
        raw_df = get_data(
            self.symbol,
            self.timeframe,
            after_ms=self.start_ms,
            limit=1000000,
            order="asc",
            indicators=self.base_indicators,
            options={**self.options, "return_polars": True}
        )

        # Abort if no data returned
        if raw_df is None or len(raw_df) == 0:
            print("🚨 [Error]: No data returned for the specified period.")
            return None, None

        # Convert Polars DataFrame to Pandas for processing
        pdf = raw_df.to_pandas()

        # Filter out market-open rows if such column exists
        if 'is-open' in pdf.columns:
            inference_df = pdf[pdf['is-open'] == 0].copy()
        else:
            inference_df = pdf.copy()

        # Abort if nothing remains after filtering
        if inference_df.empty:
            print("🚨 [Error]: No valid market-closed data points found.")
            return None, None

        # -------------------------------------------------------------
        # 2. Prepare Model Input Tensors
        # -------------------------------------------------------------
        ordered_columns = []

        # Ensure features are stacked in exact training order
        for f in self.active_features:
            if f in inference_df.columns:
                ordered_columns.append(
                    inference_df[f].fillna(0.0).values
                )
            else:
                # If feature missing, replace with zeros
                ordered_columns.append(
                    np.zeros(len(inference_df))
                )

        # Stack features into 2D float32 matrix
        raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)

        # Convert NumPy matrix into torch tensor on correct device
        raw_model_tensor = torch.from_numpy(raw_values).to(self.device)

        # Convert target indicator into binary labels
        targets = (
            inference_df[self.center].fillna(0.0) != 0
        ).astype(int).values

        total_targets = np.sum(targets)

        # -------------------------------------------------------------
        # 3. Vectorized Bulk Inference
        # -------------------------------------------------------------
        with torch.no_grad():
            # Apply training-time normalization
            normalized_tensor = (
                raw_model_tensor - self.means
            ) / (self.stds + 1e-8)

            # Forward pass
            out, _, _, _ = self.model(normalized_tensor)

            # Move predictions back to CPU NumPy
            predictions = out.squeeze().cpu().numpy()

        print(f"📊 [Data Imprint]: {len(predictions)} bars analyzed | {total_targets} total targets found.")
        print("-" * 80)

        # -------------------------------------------------------------
        # 4. Threshold Sweep
        # -------------------------------------------------------------
        thresholds = np.linspace(0.0, 1.0, steps + 1)

        best_f1_thresh = 0.0
        best_f1 = 0.0

        sniper_thresh = None
        max_sniper_tp = -1

        results = []

        # Evaluate every threshold
        for t in thresholds:
            preds = (predictions >= t).astype(int)

            tp = np.sum((preds == 1) & (targets == 1))
            fp = np.sum((preds == 1) & (targets == 0))
            fn = np.sum((preds == 0) & (targets == 1))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            # Track best F1 threshold
            if f1 > best_f1:
                best_f1 = f1
                best_f1_thresh = t

            # Track best 100% precision threshold
            if prec == 1.0 and tp > 0:
                if tp > max_sniper_tp:
                    max_sniper_tp = tp
                    sniper_thresh = t

            results.append((t, tp, fp, fn, prec, rec, f1))

        # -------------------------------------------------------------
        # 5. Sniper Fallback Handling
        # -------------------------------------------------------------
        if sniper_thresh is None:
            valid_precs = [r for r in results if r[1] > 0]
            if valid_precs:
                best_prec_result = max(valid_precs, key=lambda x: x[4])
                sniper_thresh = best_prec_result[0]
                print("⚠️ [Notice]: 100% Precision is impossible on this specific dataset.")
                print(f"   -> Settling for Max Precision Achieved: {best_prec_result[4]*100:.2f}%")
            else:
                sniper_thresh = 0.0

        # -------------------------------------------------------------
        # 6. Report Output
        # -------------------------------------------------------------
        print(f"{'Threshold':<12} | {'F1 Score':<10} | {'Precision':<10} | {'Recall':<10} | {'Hits (TP)':<10} | {'Noise (FP)':<10}")
        print("-" * 80)

        for t, tp, fp, fn, prec, rec, f1 in results:
            if round(t, 3) in [0.100, 0.300, 0.500, 0.700, 0.900]:
                print(f"{t:<12.3f} | {f1:<10.4f} | {prec:<10.4f} | {rec:<10.4f} | {tp:<10} | {fp:<10}")

        print("-" * 80)

        print("🏆 [Optimal F1 Factory Spec]:")
        print(f"   -> Threshold: {best_f1_thresh:.4f}")
        print(f"   -> F1 Score:  {best_f1:.4f}")

        print("\n🎯 [SNIPER GROUND TRUTH] (Highest Precision / Minimum Noise):")
        if sniper_thresh > 0:
            s_res = next(r for r in results if r[0] == sniper_thresh)
            print(f"   -> Threshold:   {sniper_thresh:.4f}")
            print(f"   -> Precision:   {s_res[4]*100:.2f}%")
            print(f"   -> Targets Hit: {s_res[1]} / {total_targets}")
            print(f"   -> False Alarms: {s_res[2]}")
        else:
            print("   -> 🚨 Failed to find a valid threshold that matches any targets.")

        print("=" * 80)

        return sniper_thresh, best_f1_thresh