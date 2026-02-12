from etl.exceptions import *
from etl.config.app_config import *
import pandas as pd
import numpy as np

def _apply_post_processing(o, df: pd.DataFrame, step: TransformSymbolProcessingStep) -> pd.DataFrame:
    # Validate that the requested action is supported
    if step.action not in ["validate", "add", "subtract", "multiply", "divide", "+", "-", "*", "/"]:
        raise TransformLogicError(f"Unsupported transform action: {step.action}")

    # TODO: support date ranges

    # Apply multiplication transformation
    if step.action in ["add", "subtract", "multiply", "divide", "+", "-", "*", "/"]:
        # Ensure the target column exists before modifying it
        if step.column in df.columns:
            # Convert column to float and multiply by the provided value
            if step.action in ["*", "multiply"]:
                df[step.column] = df[step.column].astype(np.float64) * step.value
            if step.action in ["+", "add"]:
                df[step.column] = df[step.column].astype(np.float64) + step.value
            if step.action in ["-", "substract"]:
                df[step.column] = df[step.column].astype(np.float64) - step.value
            if step.action in ["/", "divide"]:
                df[step.column] = df[step.column].astype(np.float64) / step.value 
            # Round to stay compliant with settings
            df[step.column] = np.round(df[step.column], o.config.round_decimals)
        else:
            # Raise an error if the column is missing
            raise ProcessingError(
                f"Symbol {o.symbol}, Column '{step.column}' not found during {step.action} step"
            )

    if step.action == "validate":
        try:
            # Logical checks for OHLC integrity
            errors = []
            if not (df['high'] >= df['low']).all():
                errors.append("High price below Low price")
            if not (df['high'] >= df[['open', 'close']].max(axis=1)).all():
                errors.append("High price below Open or Close")
            if not (df['low'] <= df[['open', 'close']].min(axis=1)).all():
                errors.append("Low price above Open or Close")
            if (df[['open', 'high', 'low', 'close']] < 0).any().any():
                errors.append("Negative prices detected")

            if errors:
                # Raise your custom exception with details
                raise DataValidationError(f"OHLC Integrity Failure: {', '.join(errors)}")

        except DataValidationError as e:
            # Todo, only log atm. Data is not flawless.
            print(f"Data validation error on {o.symbol} at date {o.dt}: {e}") 

    # Return the modified DataFrame
    return df