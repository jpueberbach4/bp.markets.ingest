import operator
import polars as pl
from ml.alerts.models import Rule

OPERATORS = {
    '>': operator.gt,
    '>=': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne
}

class RuleEvaluator:
    @staticmethod
    def evaluate(df: pl.DataFrame, rule: Rule) -> bool:
        if df is None or df.is_empty():
            return False

        latest_row = df.tail(1).to_dicts()[0]

        for condition in rule.conditions:
            if condition.column not in latest_row:
                print(f"[Evaluator] Warning: Column '{condition.column}' not found in data.")
                return False
            
            actual_value = latest_row[condition.column]
            target_value = condition.value
            op_func = OPERATORS.get(condition.operator)

            if not op_func:
                print(f"[Evaluator] Unknown operator: {condition.operator}")
                return False

            if not op_func(actual_value, target_value):
                return False
                
        return True