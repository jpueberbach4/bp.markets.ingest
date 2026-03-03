"""
===============================================================================
File:        evaluator.py
Author:      JP Ueberbach
Created:     2026-03-03

Description:
    Rule evaluation engine for ML alert processing.

    This module provides functionality for evaluating Rule objects
    against a given Polars DataFrame. It determines whether all
    conditions defined within a rule are satisfied based on the
    most recent row of data.

    Responsibilities:
        - Map string-based comparison operators to Python functions
        - Validate rule conditions against available dataset columns
        - Evaluate condition logic using the latest data snapshot
        - Return a boolean decision indicating rule satisfaction

    The evaluation strategy is:
        1. Validate input data.
        2. Extract the most recent row from the dataset.
        3. Evaluate each condition sequentially.
        4. Short-circuit on first failure.
        5. Return True only if all conditions pass.

    Designed for deterministic, stateless rule evaluation.
===============================================================================
"""

import operator
import polars as pl
from ml.alerts.models import Rule


# Mapping of supported string operators to their corresponding
# Python operator module functions for dynamic comparison execution
OPERATORS = {
    ">": operator.gt,     # Greater than
    ">=": operator.ge,    # Greater than or equal to
    "<": operator.lt,     # Less than
    "<=": operator.le,    # Less than or equal to
    "==": operator.eq,    # Equal to
    "!=": operator.ne,    # Not equal to
}


class RuleEvaluator:
    """
    Stateless evaluator for Rule objects.

    This class provides functionality to evaluate whether a given
    Rule is satisfied by the most recent row of a Polars DataFrame.

    The evaluator:
        - Uses only the latest row of the provided DataFrame
        - Evaluates conditions sequentially
        - Stops evaluation on first failed condition
        - Returns True only if all conditions pass
    """

    @staticmethod
    def evaluate(df: pl.DataFrame, rule: Rule) -> bool:
        """
        Evaluate a rule against the latest row of a DataFrame.

        Args:
            df (pl.DataFrame):
                Polars DataFrame containing indicator data.

            rule (Rule):
                Rule object containing conditions to evaluate.

        Returns:
            bool:
                True if all rule conditions are satisfied,
                False otherwise.

        Behavior:
            - Returns False if the DataFrame is None or empty.
            - Extracts the most recent row using tail(1).
            - Evaluates each condition using mapped operator functions.
            - Logs warnings for missing columns or unsupported operators.
            - Short-circuits on first failed condition.
        """

        # Validate that the DataFrame exists and contains data
        # If no data is available, the rule cannot be evaluated
        if df is None or df.is_empty():
            return False

        # Extract the latest row from the DataFrame
        # The evaluation logic operates only on the most recent snapshot
        latest_row = df.tail(1).to_dicts()[0]

        # Iterate over each condition defined in the rule
        for condition in rule.conditions:

            # Validate that the required column exists in the dataset
            # If missing, rule evaluation cannot proceed safely
            if condition.column not in latest_row:
                print(
                    f"[Evaluator] Warning: Column '{condition.column}' not found in data."
                )
                return False

            # Retrieve the actual value from the dataset
            actual_value = latest_row[condition.column]

            # Retrieve the target comparison value from the condition
            target_value = condition.value

            # Resolve the operator function from the operator mapping
            op_func = OPERATORS.get(condition.operator)

            # Validate that the operator is supported
            # If not, evaluation cannot proceed
            if not op_func:
                print(f"[Evaluator] Unknown operator: {condition.operator}")
                return False

            # Execute the comparison operation dynamically
            # If the condition fails, short-circuit and return False
            if not op_func(actual_value, target_value):
                return False

        # If all conditions pass, return True indicating rule satisfaction
        return True