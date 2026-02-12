from etl.exceptions import *
from etl.config.app_config import *
import pandas as pd
import numpy as np

def _apply_post_processing(o, df: pd.DataFrame, step: TransformSymbolProcessingStep) -> pd.DataFrame:
    """Applies post-processing transformations or validations to a symbol DataFrame.

    This function performs one of two high-level operations:

    1. Mathematical transformation (add, subtract, multiply, divide)
       on one or more DataFrame columns, optionally restricted
       to a specific date range.
    2. OHLC validation to ensure price integrity.

    The operation is determined by `step.action`.

    Args:
        o: Processing context object. Expected to contain:
            - symbol (str): Symbol name for error reporting.
            - dt: Current processing date (for logging).
            - config.round_decimals (int): Number of decimals to round to.
        df (pd.DataFrame): DataFrame containing OHLC data indexed
            by a DateTimeIndex.
        step (TransformSymbolProcessingStep): Configuration describing
            the transformation. Expected attributes:
            - action (str): Operation type.
            - columns (List[str]): Columns to modify (for math ops).
            - value (float): Value used in math operations.
            - from_date (optional): Inclusive start date filter.
            - to_date (optional): Inclusive end date filter.

    Returns:
        pd.DataFrame: The modified (or validated) DataFrame.

    Raises:
        TransformLogicError: If the action is unsupported.
        ProcessingError: If a specified column does not exist.
        DataValidationError: If OHLC validation fails.
    """

    # Make sure the requested action is something we actually support.
    # If not, fail fast and loudly.
    if step.action not in ["validate", "add", "subtract", "multiply", "divide", "+", "-", "*", "/"]:
        raise TransformLogicError(f"Unsupported transform action: {step.action}")

    # This will hold a boolean mask for date filtering.
    # If None, we apply changes to the entire DataFrame.
    mask = None

    # If a start date is provided, build a mask selecting rows >= that date.
    if hasattr(step, 'from_date') and step.from_date:
        start_ts = pd.to_datetime(step.from_date)  # Convert to proper timestamp
        mask = (df.index >= start_ts)  # True for rows we want to modify

    # If an end date is provided, extend or create a mask for rows <= that date.
    if hasattr(step, 'to_date') and step.to_date:
        end_ts = pd.to_datetime(step.to_date)  # Convert to proper timestamp
        m_end = (df.index <= end_ts)  # True for rows within upper bound
        # If we already had a mask (from from_date), combine both conditions.
        mask = m_end if mask is None else mask & m_end

    # If we defined a date range but no rows match it,
    # there is nothing to do — return immediately.
    if mask is not None and not mask.any():
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

                # If we have a mask, only operate on selected rows.
                # Otherwise, operate on the entire column.
                target = series.loc[mask] if mask is not None else series

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
                if mask is not None:
                    df.loc[mask, column] = np.round(result, o.config.round_decimals)
                else:
                    df[column] = np.round(result, o.config.round_decimals)

            else:
                # If the column is missing, this is a hard failure.
                raise ProcessingError(
                    f"Symbol {o.symbol}, Column '{column}' not found during {step.action} step"
                )

    # Handle OHLC validation.
    if step.action == "validate":
        try:
            errors = []

            # High must never be below Low.
            if not (df['high'] >= df['low']).all():
                errors.append("High price below Low price")

            # High must be >= both Open and Close.
            if not (df['high'] >= df[['open', 'close']].max(axis=1)).all():
                errors.append("High price below Open or Close")

            # Low must be <= both Open and Close.
            if not (df['low'] <= df[['open', 'close']].min(axis=1)).all():
                errors.append("Low price above Open or Close")

            # No negative prices allowed.
            if (df[['open', 'high', 'low', 'close']] < 0).any().any():
                errors.append("Negative prices detected")

            # If we collected any validation errors, raise them.
            if errors:
                raise DataValidationError(f"OHLC Integrity Failure: {', '.join(errors)}")

        except DataValidationError as e:
            # Log the validation failure but do not crash the entire process.
            print(f"Data validation error on {o.symbol} at date {o.dt}: {e}")

    # Return the modified (or validated) DataFrame.
    return df
