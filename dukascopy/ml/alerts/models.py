"""
===============================================================================
File:        models.py
Author:      JP Ueberbach
Created:     2026-03-03

Description:
    Data model definitions for the ML alerts domain.

    This module defines the core dataclass-based domain models used to
    represent alerting logic configuration, including:

        - Condition definitions for rule evaluation
        - Rule definitions composed of multiple conditions
        - Action configuration for alert execution
        - Alert job definitions that orchestrate rules and actions

    These models are designed to:
        - Provide structured, type-safe configuration handling
        - Enable clear separation between configuration parsing and execution
        - Support validation and transformation pipelines
        - Serve as canonical in-memory representations of alert configuration

    All models are implemented using Python dataclasses for simplicity,
    readability, and automatic generation of initialization and comparison
    behavior.
===============================================================================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Condition:
    """
    Represents a single logical condition within a rule.

    A Condition defines a comparison operation that will be evaluated
    against a dataset column during rule processing.

    Attributes:
        name (str):
            Human-readable identifier for the condition.

        column (str):
            Name of the dataset column to evaluate.

        operator (str):
            Comparison operator (e.g., '>', '<', '==', '>=', etc.).

        value (float):
            Numeric value used as the comparison reference.
    """

    # Human-readable identifier for the condition
    name: str

    # Target dataset column on which the condition is evaluated
    column: str

    # Comparison operator defining how the value is evaluated
    operator: str

    # Threshold or reference value used in the comparison
    value: float


@dataclass
class Rule:
    """
    Represents a rule composed of multiple evaluation conditions.

    A Rule aggregates multiple Condition instances and defines
    the logical context in which they are evaluated for a
    specific trading symbol and timeframe.

    Attributes:
        name (str):
            Unique identifier for the rule.

        symbol (str):
            Financial instrument or asset symbol (e.g., 'AAPL').

        timeframe (str):
            Timeframe used for evaluation (e.g., '1h', '1d').

        indicators (List[str]):
            List of indicator names required for rule evaluation.

        conditions (List[Condition]):
            Collection of Condition objects that define the rule logic.
    """

    # Unique name identifying the rule
    name: str

    # Target financial instrument symbol
    symbol: str

    # Evaluation timeframe for the rule
    timeframe: str

    # List of technical indicators required for evaluation
    indicators: List[str]

    # List of logical conditions that must be evaluated
    conditions: List[Condition]


@dataclass
class ActionConfig:
    """
    Represents configuration for an alert action.

    An ActionConfig defines what action should be executed when
    a rule or alert condition is satisfied.

    Attributes:
        name (str):
            Unique identifier for the action.

        type (str):
            Action type (e.g., 'email', 'webhook', 'log').

        params (Dict[str, Any]):
            Dictionary containing action-specific parameters.
    """

    # Unique name identifying the action configuration
    name: str

    # Type of action to execute (defines execution handler)
    type: str

    # Arbitrary parameters required by the action implementation
    params: Dict[str, Any]


@dataclass
class AlertJob:
    """
    Represents a scheduled alert job definition.

    An AlertJob encapsulates scheduling metadata, rule definitions,
    and associated actions to execute when rules are triggered.

    Attributes:
        name (str):
            Unique identifier for the alert job.

        weekdays (List[int]):
            List of integers representing allowed execution weekdays
            (e.g., 0=Monday, 6=Sunday).

        run_at (Optional[str]):
            Optional time-of-day string (e.g., '09:30') for execution.

        from_date (str):
            Inclusive start date for job validity.

        to_date (str):
            Inclusive end date for job validity.

        actions (List[ActionConfig]):
            List of action configurations to execute when triggered.

        rules (List[Rule]):
            List of rules evaluated as part of the job.
    """

    # Unique name identifying the alert job
    name: str

    # List of allowed weekdays for job execution
    weekdays: List[int]

    # Optional time-of-day for execution scheduling
    run_at: Optional[str]

    # Start date (inclusive) for job validity
    from_date: str

    # End date (inclusive) for job validity
    to_date: str

    # Collection of actions executed when rules are satisfied
    actions: List[ActionConfig]

    # Collection of rules evaluated within this job
    rules: List[Rule]