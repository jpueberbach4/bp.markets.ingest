"""
===============================================================================
File:        stepper.py
Author:      JP Ueberbach
Created:     2026-03-01

Description:
    Strict walk-forward evaluation module for MilkyWay models.

    This module implements a candle-by-candle forward execution simulator
    designed to eliminate look-ahead bias during validation. The model is
    evaluated sequentially, using only data available up to each step.

    Unlike bulk scanners, this module simulates real-time inference:
        - Data is fetched incrementally
        - Inference is performed on the most recent bar only
        - Signals are compared against ground-truth targets
        - Step-level diagnostics are printed in real time

    Responsibilities:
        - Reconstruct neural network from checkpoint
        - Load historical ground-truth target timestamps
        - Perform strict sequential inference
        - Track percentage price changes between steps
        - Emit step-by-step forensic trace logs

Design Notes:
    - Prevents any future leakage by design
    - Uses GPU automatically if available
    - Operates entirely in evaluation mode
    - Returns a Pandas DataFrame of walk-forward results
===============================================================================
"""
import torch
import pandas as pd
import polars as pl
import numpy as np
from typing import List, Dict
from util.api import get_data
from ml.diagnostics.base import BaseDiagnostic
from ml.diagnostics.network import SingularityInference


class ForensicWalkForward(BaseDiagnostic):
    """
    Executes strict candle-by-candle walk-forward validation.

    This class simulates real-time model deployment by incrementally
    expanding the dataset and evaluating only the most recent bar.
    """

    def __init__(
        self,
        model_path: str,
        center: str,
        symbol: str,
        timeframe: str,
        start_ms: int,
        threshold: float = None,
        options: Dict = None
    ):
        """
        Initializes the walk-forward engine.

        Args:
            model_path (str): Path to serialized model checkpoint.
            center (str): Target indicator column.
            symbol (str): Market symbol.
            timeframe (str): Data resolution.
            start_ms (int): Start timestamp in milliseconds.
            threshold (float, optional): Override decision threshold.
            options (Dict, optional): Additional API options.
        """
        # Load checkpoint and resolve device via BaseDiagnostic
        super().__init__(model_path)

        # Store dataset configuration parameters
        self.center = center
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_ms = start_ms

        # Store runtime options (default to empty dict)
        self.options = options if options else {}

        # Container for known target timestamps
        self.targets = set()

        # Total number of bars in dataset (populated later)
        self.total_bars = 0

        # Track previous closing price for % change calculation
        self.last_close = None

        # Resolve threshold: override if provided, otherwise fallback to checkpoint
        self.threshold = (
            threshold if threshold is not None
            else float(self.checkpoint.get('threshold', 0.50))
        )

        # Extract feature list from checkpoint
        self.active_features = self.checkpoint.get('feature_names', [])

        # Determine required indicators
        self.base_indicators = self._extract_indicators()

        # Reconstruct neural network
        self._load_network()

        # Load target timestamps
        self._load_targets()

    def _load_network(self):
        """
        Constructs neural network and loads checkpoint weights.

        Returns:
            None
        """
        # Load normalization tensors onto correct device
        self.means = self.checkpoint['means'].to(self.device)
        self.stds = self.checkpoint['stds'].to(self.device)

        # Load first-layer weights and biases
        w1 = self.checkpoint['W1'].to(self.device)
        b1 = self.checkpoint['B1'].to(self.device).reshape(-1)

        # Load second-layer weights and biases
        w2 = self.checkpoint['W2'].to(self.device)
        b2 = self.checkpoint['B2'].to(self.device).reshape(-1)

        # Determine architecture dimensions
        in_dim, hid_dim = w1.shape

        # Instantiate inference model
        self.model = SingularityInference(
            input_dim=in_dim,
            hidden_dim=hid_dim
        ).to(self.device)

        # Assign learned parameters (transpose for PyTorch layout)
        self.model.l1.weight.data = w1.t()
        self.model.l1.bias.data = b1

        final_w2 = w2 if w2.shape[0] == 1 else w2.t()
        self.model.l2.weight.data = final_w2
        self.model.l2.bias.data = b2

        # Set model to evaluation mode
        self.model.eval()

    def _extract_indicators(self) -> List[str]:
        """
        Determines required indicators for inference.

        Returns:
            List[str]: Unique indicator names.
        """
        unique_indicators = set()

        # Extract base names from feature list
        for feature in self.active_features:
            base_name = feature.split(':')[0].split('__')[0]
            unique_indicators.add(base_name)

        # Always include market state flag
        unique_indicators.add("is-open")

        # Ensure close price exists for percentage calculation
        if "close" not in unique_indicators:
            unique_indicators.add("close")

        return list(unique_indicators)

    def _load_targets(self):
        """
        Loads ground-truth target timestamps.

        Returns:
            None
        """
        print(f"🔍 [Forensic Stepper]: Mapping target coordinates for '{self.center}'...")

        center_df = get_data(
            self.symbol,
            self.timeframe,
            after_ms=self.start_ms,
            limit=1000000,
            order="asc",
            indicators=[self.center],
            options={**self.options, "return_polars": True}
        )

        # Record total bars available
        self.total_bars = len(center_df)

        # Extract timestamps where target indicator is non-zero
        target_times = center_df.filter(
            pl.col(self.center) != 0
        )["time_ms"].to_list()

        # Store as set for O(1) membership lookup
        self.targets = set(target_times)

        print(f"🎯 [Forensic Stepper]: Extracted {len(self.targets)} confirmed targets.")

    def _run_inference(self, raw_df: pl.DataFrame) -> float:
        """
        Runs inference on the most recent available bar.

        Args:
            raw_df (pl.DataFrame): Incrementally expanded dataset.

        Returns:
            float: Latest prediction score.
        """
        # Convert to Pandas for feature extraction
        pdf = raw_df.to_pandas()

        # Filter out market-open rows if present
        if 'is-open' in pdf.columns:
            inference_df = pdf[pdf['is-open'] == 0].copy()
        else:
            inference_df = pdf.copy()

        # If no usable data exists, return neutral score
        if inference_df.empty:
            return 0.0

        # Only use the most recent row
        inference_df = inference_df.tail(1)

        ordered_columns = []

        # Maintain strict feature order
        for f in self.active_features:
            if f in inference_df.columns:
                ordered_columns.append(
                    inference_df[f].fillna(0.0).values
                )
            else:
                ordered_columns.append(
                    np.zeros(len(inference_df))
                )

        # Stack features into tensor
        raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)
        raw_model_tensor = torch.from_numpy(raw_values).to(self.device)

        with torch.no_grad():
            # Apply normalization
            normalized_tensor = (
                raw_model_tensor - self.means
            ) / (self.stds + 1e-8)

            # Forward pass
            out, _, _, _ = self.model(normalized_tensor)
            predictions = out.squeeze().cpu().numpy()

            # Ensure array shape consistency
            if predictions.ndim == 0:
                predictions = np.array([predictions.item()])

        return float(predictions[-1])

    def run(self, max_steps: int = -1) -> pd.DataFrame:
        """
        Executes walk-forward simulation.

        Args:
            max_steps (int): Maximum number of steps to execute.

        Returns:
            pd.DataFrame: Step-by-step execution results.
        """
        from datetime import datetime, timezone

        print(f"\n🚀 [Forensic Stepper]: Initiating Walk-Forward Execution.")
        print(f"📦 Active Model: {self.model_name} | Threshold: {self.threshold:.4f}")
        print("-" * 105)

        walk_results = []

        # Determine number of steps to execute
        num_steps = max_steps if max_steps > 0 else self.total_bars

        # Fetch the data
        base_df = get_data(
            self.symbol,
            self.timeframe,
            after_ms=self.start_ms,
            limit=self.total_bars,
            order="asc",
            indicators=self.base_indicators,
            options={**self.options, "return_polars": True}
        )

        if base_df is None or len(base_df) == 0:
            return

        for step in range(1, num_steps + 1):

            # Fetch data incrementally up to current step
            raw_df = base_df[:step]

            # Run inference on latest bar
            
            # Note: although we use the tail(1) in run, we could theoretically pass
            # only the last record. However, future plans include support for RNN.
            # RNN looks at more "previous records" than only the last row. To support
            # this, we leave this stuff in-place. For now. Until we know exactly how
            # many rows a model "looks-back" (we need to store that info in the mode).
            # RNN will be another great addition. Stay tuned.

            # Note: although the last record may be is-open == 1, we pass it in. Any
            # last open record will get the score value of the previous-last record.
            # Inference is run on tail(1) in run_reference. 0:step is passed in, never
            # empty slice. tail(1) has always a record. 

            latest_score = self._run_inference(raw_df)

            # Determine signal state
            latest_signal = "🟢 FIRE" if latest_score >= self.threshold else ""

            # Extract latest bar state
            latest_state = raw_df.tail(1).to_dicts()[0]
            latest_state["ml_score"] = latest_score
            latest_state["ml_signal"] = (
                1.0 if latest_score >= self.threshold else 0.0
            )

            # Compute percentage change in close price
            current_close = latest_state.get("close", 0.0)
            pct_change = 0.0

            if self.last_close is not None and self.last_close != 0:
                pct_change = (
                    (current_close - self.last_close)
                    / self.last_close
                ) * 100

            self.last_close = current_close

            # Determine if current timestamp matches ground truth
            is_center_signal = latest_state["time_ms"] in self.targets
            latest_state["is_target"] = is_center_signal

            walk_results.append(latest_state)

            pct_str = f"{pct_change:+.4f}%"
            target_str = "🎯 HIT" if is_center_signal else ""

            # Convert timestamp to readable UTC string
            time_ms = latest_state.get("time_ms", 0)
            dt_str = datetime.fromtimestamp(
                time_ms / 1000.0,
                tz=timezone.utc
            ).strftime('%Y-%m-%d %H:%M:%S')

            # Print step-level trace
            print(
                f"Step {step:>4}/{num_steps} | "
                f"Time: {dt_str} | "
                f"Bars: {len(raw_df):>4} | "
                f"Close: {current_close:>9.5f} ({pct_str:<9}) | "
                f"Score: {latest_score:>.6f} | "
                f"{latest_signal:<8} {target_str}"
            )

        print("-" * 105)
        print("✅ [Forensic Stepper]: Walk-Forward Complete.\n")

        return pd.DataFrame(walk_results)