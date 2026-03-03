from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Condition:
    name: str
    column: str
    operator: str
    value: float

@dataclass
class Rule:
    name: str
    symbol: str
    timeframe: str
    indicators: List[str]
    conditions: List[Condition]

@dataclass
class ActionConfig:
    name: str
    type: str
    params: Dict[str, Any]

@dataclass
class AlertJob:
    name: str
    weekdays: List[int]
    run_at: Optional[str]
    from_date: str
    to_date: str
    actions: List[ActionConfig]
    rules: List[Rule]