from etl.exceptions import *
from etl.config.app_config import *
import pandas as pd
import numpy as np

def _apply_post_processing(o, df: pd.DataFrame, step: TransformSymbolProcessingStep) -> pd.DataFrame:
    """Applies post-processing transformations or validations to a symbol DataFrame."""

    # Guard against empty DataFrames (The BRENT-CMD fix)
    if df.empty:
        return df

    # Extract boundaries (Assume these are pre-converted or use pd.to_datetime)
    # Using getattr for safety with the Step dataclass
    from_date = getattr(step, 'from_date', None)
    to_date = getattr(step, 'to_date', None)

    # Resolve actual timestamps if strings were provided
    rule_start = pd.to_datetime(from_date) if from_date else None
    rule_end = pd.to_datetime(to_date) if to_date else None

    # O(1) Short-circuit: Check if DataFrame is entirely outside the rule window
    # Only perform if dates are actually provided in the step
    if rule_start or rule_end:
        data_start = df.index[0]
        data_end = df.index[-1]
        
        # If data is completely after the rule or completely before it, skip.
        if (rule_end and data_start > rule_end) or (rule_start and data_end < rule_start):
            return df

    # We use searchsorted for O(log n) lookup to find the integer slice bounds.
    # This replaces the O(n) boolean mask scanning.
    start_idx = 0
    end_idx = len(df)

    if rule_start:
        start_idx = df.index.searchsorted(rule_start, side='left')

    if rule_end:
        end_idx = df.index.searchsorted(rule_end, side='right')

    # If the range results in no rows, return immediately.
    if start_idx >= end_idx:
        return df

    # Handle arithmetic transformations.
    if step.action in ["add", "subtract", "multiply", "divide", "+", "-", "*", "/"]:
        # Loop through each column we are supposed to modify.
        for column in step.columns:
            # Ensure the column actually exists.
            if column in df.columns:

                # Convert to float64 to avoid precision issues
                # and ensure math operations behave consistently.
                series = df[column].astype(np.float64)

                # Use integer slicing (iloc) to create a view of the target data.
                target = series.iloc[start_idx:end_idx]

                # Perform the correct math operation.
                if step.action in ["*", "multiply"]:
                    result = target * step.value
                elif step.action in ["+", "add"]:
                    result = target + step.value
                elif step.action in ["-", "subtract"]:
                    result = target - step.value
                elif step.action in ["/", "divide"]:
                    result = target / step.value

                # Write the result back into the DataFrame,
                # rounding to configured decimal precision.
                df.iloc[start_idx:end_idx, df.columns.get_loc(column)] = np.round(result, o.config.round_decimals)

            else:
                # If the column is missing, this is a hard failure.
                raise ProcessingError(
                    f"Symbol {o.symbol}, Column '{column}' not found during {step.action} step"
                )

    # Handle OHLC validation.
    if step.action == "validate":
        try:
            # For validation, we focus on the relevant slice of the data.
            v_df = df.iloc[start_idx:end_idx]
            errors = []

            # High must never be below Low.
            if not (v_df['high'] >= v_df['low']).all():
                errors.append("High price below Low price")

            # High must be >= both Open and Close.
            if not (v_df['high'] >= v_df[['open', 'close']].max(axis=1)).all():
                errors.append("High price below Open or Close")

            # Low must be <= both Open and Close.
            if not (v_df['low'] <= v_df[['open', 'close']].min(axis=1)).all():
                errors.append("Low price above Open or Close")

            # No negative prices allowed.
            if (v_df[['open', 'high', 'low', 'close']] < 0).any().any():
                errors.append("Negative prices detected")

            # If we collected any validation errors, raise them.
            if errors:
                raise DataValidationError(f"OHLC Integrity Failure: {', '.join(errors)}")

        except DataValidationError as e:
            # Log the validation failure but do not crash the entire process.
            print(f"Data validation error on {o.symbol} at date {o.dt}: {e}")

    # Return the modified (or validated) DataFrame.
    return df
