"""
===============================================================================
File:        sinpector.py
Author:      JP Ueberbach
Created:     2026-03-01

Description:
    Diagnostic inspection module for persisted MilkyWay model checkpoints.

    This module implements a concrete diagnostic tool responsible for
    performing post-hoc forensic analysis of trained or evolved models.
    It inspects architectural parameters, normalization statistics, and
    first-layer weight magnitudes to surface potential data or training
    pathologies.

    The inspector operates entirely in read-only mode and does not mutate
    model state. All analysis is derived from values stored in the model
    checkpoint dictionary.

Responsibilities:
    - Load and interpret normalization statistics (means / stds)
    - Detect anomalous feature scaling conditions
    - Report model architecture dimensions
    - Compute and rank per-feature importance from first-layer weights
    - Emit human-readable diagnostic summaries to stdout

Design Notes:
    - Inherits checkpoint loading and device handling from BaseDiagnostic
    - Assumes a single-output architecture
    - Importance analysis is limited to 2D first-layer weight tensors
    - All failures degrade gracefully with warnings, not exceptions
===============================================================================
"""
import numpy as np
import pandas as pd
from ml.diagnostics.base import BaseDiagnostic
from ml.diagnostics.network import SingularityInference


class ModelInspector(BaseDiagnostic):
    """
    Performs forensic analysis on neuro-evolved model checkpoints.

    This diagnostic examines stored model parameters to identify potential
    issues related to feature normalization, architectural configuration,
    and relative gene (feature) influence.
    """

    def __init__(self, model_path: str):
        """
        Initializes the model inspector.

        Args:
            model_path (str): Filesystem path to the serialized model
                checkpoint to be analyzed.
        """
        # Delegate all initialization logic to the BaseDiagnostic
        super().__init__(model_path)

    def run(self):
        """
        Executes the full inspection pipeline.

        This method extracts metadata, validates normalization statistics,
        computes feature importance scores, and prints a structured report
        to standard output.

        Returns:
            None
        """
        # Announce the start of the inspection so the user knows something is happening
        print(f"\n🧬 [Model Inspector]: Initiating Deep Scan of '{self.model_name}'")
        print("=" * 70)

        # Pull the list of active feature names from the checkpoint, or use an empty list
        active_features = self.checkpoint.get('feature_names', [])

        # Retrieve the model decision threshold, defaulting to 0.50 if missing
        threshold = float(self.checkpoint.get('threshold', 0.50))

        # Extract normalization means and move them from torch tensors to NumPy arrays
        means = self.checkpoint['means'].cpu().numpy()

        # Extract normalization standard deviations and convert to NumPy
        stds = self.checkpoint['stds'].cpu().numpy()

        # Load first-layer weights and move them to CPU NumPy arrays
        w1 = self.checkpoint['W1'].cpu().numpy()

        # Load second-layer weights (not used for importance, but relevant for shape sanity)
        w2 = self.checkpoint['W2'].cpu().numpy()

        # Infer input dimensionality based on the shape of the first-layer weights
        input_dim = w1.shape[1] if len(w1.shape) > 1 else w1.shape[0]

        # Infer hidden dimensionality, assuming a single hidden layer
        hidden_dim = w1.shape[0] if len(w1.shape) > 1 else 1

        # Emit basic architectural metadata
        print(f"📦 [Architecture]: Input Dim: {input_dim} | Hidden Dim: {hidden_dim} | Out Dim: 1")
        print(f"🎯 [Threshold]:   {threshold:.6f}")
        print(f"🧬 [Gene Count]:   {len(active_features)}")
        print("-" * 70)

        # Begin validation of normalization statistics
        print("🔬 [Normalization Diagnostics]: Checking for Z-Mean/Std anomalies...")

        # Track how many problematic features are detected
        anomaly_count = 0

        # Accumulate per-feature normalization diagnostics for tabular processing
        norm_data = []

        # Iterate over each declared feature and its index
        for idx, feature in enumerate(active_features):
            # Safely retrieve the mean value for this feature, or default to zero
            f_mean = means[idx] if idx < len(means) else 0.0

            # Safely retrieve the standard deviation, or default to zero
            f_std = stds[idx] if idx < len(stds) else 0.0

            # Assume the feature is healthy until proven otherwise
            status = "OK"

            # Flag near-zero variance, which indicates a dead or constant feature
            if f_std < 1e-6:
                status = "🚨 DANGER: Zero Variance (Flatline)"
                anomaly_count += 1

            # Flag absurdly large mean values that suggest scaling errors
            elif abs(f_mean) > 1000:
                status = "⚠️ WARNING: Extreme Mean Offset"
                anomaly_count += 1

            # Record the diagnostic outcome for this feature
            norm_data.append({
                "Feature": feature,
                "Mean": f_mean,
                "StdDev": f_std,
                "Status": status
            })

        # Convert the collected diagnostics into a DataFrame for iteration
        norm_df = pd.DataFrame(norm_data)

        # Print only features that are not considered healthy
        for _, row in norm_df.iterrows():
            if row["Status"] != "OK":
                print(
                    f"   -> [{row['Feature']}] "
                    f"Mean: {row['Mean']:.2f} | "
                    f"Std: {row['StdDev']:.2f} | "
                    f"{row['Status']}"
                )

        # If nothing went wrong, explicitly state that everything is fine
        if anomaly_count == 0:
            print("   ✅ All normalization vectors look healthy.")
        print("-" * 70)

        # Begin analysis of feature influence using first-layer weights
        print("📊 [Gene Importance Analysis]: Ranking structural impact...")

        # Only proceed if the weight tensor has the expected 2D shape
        if len(w1.shape) == 2:
            # Compute per-input importance as the sum of absolute weights
            importance_scores = np.sum(np.abs(w1), axis=0)

            # Compute the total importance mass for normalization
            total_importance = np.sum(importance_scores)

            # Normalize importance scores to percentages if possible
            if total_importance > 0:
                importance_scores = (importance_scores / total_importance) * 100

            # Collect feature-to-score mappings
            importance_data = []

            # Associate each feature with its corresponding importance score
            for idx, feature in enumerate(active_features):
                score = importance_scores[idx] if idx < len(importance_scores) else 0.0
                importance_data.append((feature, score))

            # Sort features by descending importance
            importance_data.sort(key=lambda x: x[1], reverse=True)

            # Print ranked importance list
            for rank, (feature, score) in enumerate(importance_data, 1):
                print(f"   {rank:>2}. {feature:<50} | Impact: {score:>5.2f}%")
        else:
            # Abort importance analysis if tensor shape is not interpretable
            print("   ⚠️ Cannot calculate importance: W1 tensor format unrecognized.")

        # Close out the report cleanly
        print("=" * 70)
        print("✅ [Model Inspector]: Deep Scan Complete.\n")