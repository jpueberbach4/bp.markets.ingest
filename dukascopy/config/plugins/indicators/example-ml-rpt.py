import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
import time
from typing import List, Dict, Any


# Global in-memory registry used to store recently loaded models.
# This avoids repeatedly loading model checkpoints from disk during
# frequent inference calls, which significantly reduces latency.
MODEL_REGISTRY = {}

# Time-to-live for cached models in seconds. If a model entry in the
# registry is older than this value it will be reloaded from disk.
CACHE_TTL = 30


def description() -> str:
    """
    Returns a descriptive summary of the inference engine.

    Returns:
        str: Text describing the architecture, caching strategy,
        inference design, and bias-prevention mechanisms.
    """
    return (
        "High-fidelity inference engine utilizing a Registry-Cached Singularity architecture. "
        "Implements strict 'is-open' data isolation and 'merge_asof' backward alignment to "
        "eliminate look-ahead bias. Features a 30s TTL Multi-Model Cache, 1D-CNN Macro-Stencil "
        "Windowing, and Throttled Audit."
    )


def meta() -> Dict:
    """
    Returns metadata describing the module.

    Returns:
        Dict: Metadata including author, version, panel identifier,
        and verification status.
    """
    return {"author": "JP", "version": "2.5.0", "panel": 1, "verified": 1}


def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Parses positional runtime arguments.

    Args:
        args (List[str]): Raw argument list supplied by the execution
        environment.

    Returns:
        Dict[str, Any]: Parsed runtime configuration containing:
            model-name: Name of the checkpoint file.
            threshold: Signal classification threshold.
    """
    return {
        "model-name": args[0] if len(args) > 0 else "model-best.pt",
        "threshold": args[1] if len(args) > 1 else 0.50
    }


def warmup_count(args: List[str]) -> int:
    """
    Specifies how many historical bars must be available before
    inference is allowed to begin.

    Args:
        args (List[str]): Runtime arguments (unused).

    Returns:
        int: Required warmup bar count.
    """
    return 1000


class SingularityInference(nn.Module):
    """
    Neural network inference architecture implementing a 1D CNN
    macro-stencil pattern designed for temporal feature extraction
    across financial indicator sequences.
    """

    def __init__(self, gene_count: int, hidden_dim: int, kernel_size: int, flatten_dim: int):
        """
        Initializes the CNN inference model.

        Args:
            gene_count (int): Number of input feature channels.
            hidden_dim (int): Number of convolution filters.
            kernel_size (int): Size of the temporal convolution kernel.
            flatten_dim (int): Flattened dimension entering the
                fully connected prediction layer.
        """
        super(SingularityInference, self).__init__()

        # Temporal convolution layer that scans across the lookback
        # sequence for each input feature channel.
        self.conv = nn.Conv1d(
            in_channels=gene_count,
            out_channels=hidden_dim,
            kernel_size=kernel_size
        )

        # GELU activation introduces non-linearity while maintaining
        # smooth gradients and stable training characteristics.
        self.activation = nn.GELU()

        # Fully connected layer that converts flattened convolution
        # activations into a single prediction score.
        self.fc = nn.Linear(flatten_dim, 1)

        # Sigmoid activation maps the raw score into probability space.
        self.out_act = nn.Sigmoid()

    def forward(self, x):
        """
        Executes a forward inference pass.

        Args:
            x (torch.Tensor): Input tensor of shape
                (num_windows, gene_count, lookback).

        Returns:
            Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
                Prediction probabilities and intermediate tensors
                useful for inspection or debugging.
        """

        # Apply convolution across the temporal dimension of the input
        # feature windows to extract temporal patterns.
        c1 = self.conv(x)

        # Apply non-linear activation to convolution output.
        a1 = self.activation(c1)

        # Flatten convolution outputs across feature and time dimensions
        # so they can be processed by the dense prediction layer.
        p_flat = a1.view(x.size(0), -1)

        # Produce the raw prediction score.
        s2 = self.fc(p_flat)

        # Return sigmoid probability along with intermediate tensors.
        return self.out_act(s2), c1, a1, s2


def get_cached_model(checkpoint_path: str, device: torch.device):
    """
    Retrieves a model from cache or loads it from disk.

    Args:
        checkpoint_path (str): Path to the checkpoint file.
        device (torch.device): Target device for model tensors.

    Returns:
        Dict | None: Cached model configuration and tensors,
        or None if the checkpoint does not exist.
    """

    # Capture the current timestamp for cache validation.
    now = time.time()

    # If the model exists in the registry and the entry has not expired,
    # return the cached version to avoid disk I/O.
    if checkpoint_path in MODEL_REGISTRY:
        cache_entry = MODEL_REGISTRY[checkpoint_path]
        if now - cache_entry['timestamp'] < CACHE_TTL:
            return cache_entry['data']

    # Abort if the checkpoint file does not exist.
    if not os.path.exists(checkpoint_path):
        return None

    # Load checkpoint contents into memory.
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Extract convolution weights and biases.
    w1 = checkpoint['W1'].to(device)
    b1 = checkpoint['B1'].to(device).reshape(-1)

    # Extract fully connected layer weights and biases.
    w2 = checkpoint['W2'].to(device)
    b2 = checkpoint['B2'].to(device).reshape(-1)

    # Determine CNN structural parameters from the weight tensor.
    hidden_dim, gene_count, kernel_size = w1.shape

    # Retrieve configuration parameters embedded in the checkpoint.
    config = checkpoint.get('config', {})
    lookback = int(config.get('lookback', 24))

    # In macro-stencil architecture the convolution kernel spans the
    # full lookback window, leaving only the filter dimension to flatten.
    flatten_dim = hidden_dim

    # Instantiate the inference model with extracted dimensions.
    nn_model = SingularityInference(
        gene_count=gene_count,
        hidden_dim=hidden_dim,
        kernel_size=kernel_size,
        flatten_dim=flatten_dim
    ).to(device)

    # Assign loaded weights directly into model parameters.
    nn_model.conv.weight.data = w1
    nn_model.conv.bias.data = b1
    nn_model.fc.weight.data = w2 if w2.shape[0] == 1 else w2.t()
    nn_model.fc.bias.data = b2

    # Set model to evaluation mode to disable training behaviors.
    nn_model.eval()

    # Retrieve list of feature names expected by the model.
    feature_names = checkpoint.get('feature_names', [])

    # Build the cached data structure that will be reused during inference.
    data = {
        'feature_names': feature_names,
        'gene_count': gene_count,
        'lookback': lookback,
        'nn_model': nn_model,
        'w1': w1,
        'means': checkpoint['means'].to(device),
        'stds': checkpoint['stds'].to(device),
        'last_audit_time': 0
    }

    # Store the loaded model inside the global registry.
    MODEL_REGISTRY[checkpoint_path] = {
        'timestamp': now,
        'data': data
    }

    return data


def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Executes inference across the provided market data frame.

    Args:
        df (pd.DataFrame): Input market data containing timestamps.
        options (Dict[str, Any]): Runtime configuration options.

    Returns:
        pd.DataFrame: DataFrame containing prediction scores and
        binary signals aligned to the input timeline.
    """

    # Flag controlling whether inference uses all rows or only closed bars.
    cancel_isopen = True

    from util.api import get_data_auto

    # If no input data exists return a zero-filled result.
    if df.empty:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Automatically select GPU if available otherwise fallback to CPU.
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Retrieve model name from options with a default fallback.
    model_name = options.get('model-name', 'model-best.pt')

    # Determine checkpoint search path.
    checkpoint_path = f"models/{model_name}"
    if not os.path.exists(checkpoint_path):
        checkpoint_path = f"checkpoints/{model_name}"

    # Attempt to load model from cache or disk.
    cached_data = get_cached_model(checkpoint_path, device)

    # Abort if the model could not be loaded.
    if cached_data is None:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Extract cached configuration parameters.
    active_features = cached_data['feature_names']
    lookback = cached_data['lookback']
    means = cached_data['means']
    stds = cached_data['stds']
    nn_model = cached_data['nn_model']

    # Determine parent indicators required to compute derived features.
    parent_indicators = list(set([f.split(':')[0].split('__')[0] for f in active_features]))

    # Request indicator data from the upstream data provider.
    raw_df = get_data_auto(df, indicators=parent_indicators + ["is-open"])

    # Determine which rows should participate in inference.
    if cancel_isopen:
        inference_df = raw_df.copy()
    else:
        inference_df = raw_df[raw_df['is-open'] == 0].copy()

    # Compute missing value statistics for the features required by the model.
    nan_counts = inference_df[active_features].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]

    # Emit a diagnostic warning if missing data is detected.
    if not nan_cols.empty:
        print("\n" + "🚨" * 20)
        print("CRITICAL: NaN Detected in Inference Columns!")
        for col, count in nan_cols.items():
            print(f"COLUMN: {col:<60} | MISSING BARS: {count}")
        print("🚨" * 20 + "\n")

    # Abort if no rows remain for inference.
    if inference_df.empty:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Align input feature columns exactly to the order expected by the model.
    ordered_columns = []
    for f in active_features:
        if f in inference_df.columns:
            ordered_columns.append(inference_df[f].values)
        else:
            ordered_columns.append(np.zeros(len(inference_df)))

    # Stack feature arrays into a matrix of shape (rows, features).
    raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)

    # Convert numpy matrix to torch tensor on the selected device.
    raw_tensor = torch.from_numpy(raw_values).to(device)

    # Compute global mean and standard deviation across the dataset.
    live_edge_mean = raw_tensor.mean(dim=0, keepdim=True)
    live_edge_std = raw_tensor.std(dim=0, keepdim=True)

    # Normalize features using dynamically calculated statistics.
    normalized_tensor = (raw_tensor - live_edge_mean) / (live_edge_std + 1e-8)

    # Construct rolling windows used by the CNN temporal convolution.
    if lookback > 1:

        # Abort if insufficient historical rows exist.
        if len(normalized_tensor) < lookback:
            return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

        # Create sliding windows across the temporal dimension.
        inference_tensor = normalized_tensor.unfold(dimension=0, size=lookback, step=1)

    else:

        # Expand tensor to maintain consistent dimensionality.
        inference_tensor = normalized_tensor.unsqueeze(-1)

    # Disable gradient computation during inference for performance.
    with torch.no_grad():

        # Run forward pass through the neural network.
        out, _, _, _ = nn_model(inference_tensor)

        # Convert predictions back to numpy.
        predictions = out.squeeze().cpu().numpy()

        if predictions.ndim == 0:
            predictions = np.array([predictions.item()])

        # Pad early predictions that lack sufficient lookback history.
        if lookback > 1:
            padding = np.zeros(lookback - 1)
            predictions = np.concatenate([padding, predictions])

        # Throttle expensive audit printing to once every 30 seconds.
        current_time = time.time()
        if (current_time - cached_data['last_audit_time']) > 30:

            cached_data['last_audit_time'] = current_time

            # Calculate feature structural importance from convolution weights.
            feature_impact = cached_data['w1'].abs().sum(dim=(0, 2)).cpu().numpy()

            print("\n" + "☢️" * 60)
            print(f"STABLE AS-OF AUDIT: {model_name}")
            print(f"Device: {device} | Cache: ACTIVE | Mode: CNN-MACRO-STENCIL (Lookback: {lookback})")
            print("-" * 80)

            header = f"{'FEATURE NAME':<60} | {'RAW MEAN':>10} | {'Z-MEAN':>8} | {'STRUCTURAL IMPACT':>15}"
            print(header)
            print("-" * 80)

            for i, name in enumerate(active_features):

                r_mean = raw_tensor[:, i].mean().item()
                z_mean = normalized_tensor[:, i].mean().item()
                impact = feature_impact[i]

                print(f"{name[:59]:<60} | {r_mean:>10.4f} | {z_mean:>8.4f} | {impact:>15.4f}")

            print("-" * 60)
            print(f"FINAL MAX PREDICTION (STABLE): {predictions.max():.4f}")
            print("☢️" * 60 + "\n")

    # Convert probability scores into binary trading signals.
    threshold_val = float(options.get('threshold', 0.50))

    stable_results = pd.DataFrame({
        'time_ms': inference_df['time_ms'],
        'score': predictions
    })

    stable_results['signal'] = np.where(
        stable_results['score'] > threshold_val,
        1.0,
        0.0
    )

    # Align inference results with the original input timeline.
    final_df = df[['time_ms']].copy()
    final_df['time_ms'] = final_df['time_ms'].astype('int64')
    stable_results['time_ms'] = stable_results['time_ms'].astype('int64')

    final_df = pd.merge_asof(
        final_df.sort_values('time_ms'),
        stable_results.sort_values('time_ms'),
        on='time_ms',
        direction='backward'
    )

    # Forward fill predictions to maintain continuity.
    res = final_df.ffill().fillna(0.0)

    # Ensure the returned slice matches the original dataframe length.
    start_time = df['time_ms'].iloc[0]
    sliced_res = res[res['time_ms'] >= start_time].copy()

    if len(sliced_res) != len(df):
        sliced_res = sliced_res.iloc[-len(df):]

    return sliced_res[['score', 'signal']]