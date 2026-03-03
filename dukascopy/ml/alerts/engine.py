"""
===============================================================================
File:        engine.py
Author:      JP Ueberbach
Created:     2026-03-03

Description:
    Core alert processing engine for ML-based rule evaluation.

    This module defines the AlertEngine, responsible for:

        - Parsing raw configuration into structured domain models
        - Applying scheduling constraints (weekday, date range, run time)
        - Fetching market or indicator data from external APIs
        - Evaluating rules using the RuleEvaluator
        - Dispatching configured actions when rules are triggered

    Processing Flow:
        1. Parse configuration into AlertJob objects.
        2. On execution, validate schedule constraints.
        3. Fetch required data per rule.
        4. Evaluate rule conditions.
        5. Dispatch actions if rule is triggered.

    The engine is designed to be deterministic, configuration-driven,
    and easily extensible via new rule types and action handlers.
===============================================================================
"""

import time
from datetime import datetime
from typing import List, Dict, Any
from ml.alerts.models import AlertJob, ActionConfig, Rule, Condition
from ml.alerts.evaluator import RuleEvaluator
from ml.alerts.actions import ActionFactory
from util.api import get_data
import re


class AlertEngine:
    """
    Orchestrates alert job scheduling, rule evaluation, and action dispatch.

    The AlertEngine converts raw configuration into structured AlertJob
    objects and executes them based on scheduling rules and data-driven
    condition evaluation.
    """

    def __init__(self, config: Any):
        """
        Initialize the AlertEngine.

        Args:
            config (Any):
                Raw configuration object containing alert job definitions.
        """
        # Store the raw configuration reference for potential future use
        self.config = config

        # Parse raw configuration into structured AlertJob instances
        self.jobs = self._parse_config(config)

    def _parse_config(self, raw: Any) -> List[AlertJob]:
        """
        Parse raw configuration into AlertJob objects.

        Args:
            raw (Any):
                Raw configuration mapping job names to configuration blocks.

        Returns:
            List[AlertJob]:
                List of parsed and structured alert jobs.
        """
        # Initialize list to collect parsed jobs
        jobs = []

        # Iterate through each configured job definition
        for job_name, data in raw.items():

            # Initialize action collection for this job
            actions = []

            # Iterate through configured actions for the job
            for name, params in data.get("actions", {}).items():
                # Log action module loading for traceability
                print(f"Loading action module: {name}")

                # Create ActionConfig instance for each action definition
                actions.append(
                    ActionConfig(
                        name=name,
                        type=params.get("type"),
                        params=params,
                    )
                )

            # Initialize rule collection for this job
            rules = []

            # Iterate through configured rules
            for r in data.get("rules", []):

                # Extract rule name (single-key dictionary pattern)
                r_name = list(r.keys())[0]

                # Extract rule configuration block
                r_data = r[r_name]

                # Initialize condition collection for this rule
                conditions = []

                # Iterate through configured conditions
                for c in r_data.get("conditions", []):

                    # Extract condition name (single-key dictionary pattern)
                    c_name = list(c.keys())[0]

                    # Extract condition configuration block
                    c_data = c[c_name]

                    # Create Condition instance
                    conditions.append(
                        Condition(
                            name=c_name,
                            column=c_data["column"],
                            operator=c_data["operator"],
                            value=c_data["value"],
                        )
                    )

                # Create Rule instance with parsed conditions
                rules.append(
                    Rule(
                        name=r_name,
                        symbol=r_data["symbol"],
                        timeframe=r_data["timeframe"],
                        indicators=r_data["indicators"],
                        conditions=conditions,
                    )
                )

            # Create AlertJob instance with parsed rules and actions
            jobs.append(
                AlertJob(
                    name=job_name,
                    weekdays=data.get("weekdays", []),
                    run_at=data.get("run-at"),
                    from_date=data.get("from_date"),
                    to_date=data.get("to_date"),
                    actions=actions,
                    rules=rules,
                )
            )

        # Return fully parsed job list
        return jobs

    def process_jobs(self):
        """
        Execute alert jobs based on scheduling and rule evaluation.

        This method:
            - Validates weekday constraints
            - Validates date range constraints
            - Validates run-at pattern (supports wildcard '*')
            - Fetches required data per rule
            - Evaluates rule conditions
            - Dispatches configured actions if triggered
        """
        # Capture current system time for scheduling evaluation
        current_time = datetime.now()

        # Determine current weekday (0=Monday, 6=Sunday)
        current_weekday = current_time.weekday()

        # Format current time to HH:MM:00 string for pattern matching
        current_hms = current_time.strftime("%H:%M:00")

        # Iterate over all configured jobs
        for job in self.jobs:

            # Skip job if current weekday is not allowed
            if current_weekday not in job.weekdays:
                continue

            # Validate job date range constraints
            try:
                fmt = "%Y-%m-%d"

                # Normalize job start date
                job_start = (
                    job.from_date
                    if isinstance(job.from_date, datetime)
                    else datetime.strptime(str(job.from_date), fmt)
                )

                # Normalize job end date
                job_end = (
                    job.to_date
                    if isinstance(job.to_date, datetime)
                    else datetime.strptime(str(job.to_date), fmt)
                )

                # Skip job if outside configured date window
                if not (job_start <= current_time <= job_end):
                    continue

            except Exception as e:
                # Log date parsing errors and skip job
                print(f"[Schedule Error] Date parsing failed for job {job.name}: {e}")
                continue

            # Validate run-at pattern if defined (supports '*' wildcard)
            if job.run_at and str(job.run_at).strip():

                # Replace wildcard '*' with regex two-character matcher
                pattern_str = str(job.run_at).replace("*", "..")

                # Anchor regex to match full string
                pattern = f"^{pattern_str}$"

                # Skip job if current time does not match pattern
                if not re.match(pattern, current_hms):
                    continue

            # Log job execution start
            print(
                f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Executing Job: {job.name}"
            )

            # Evaluate each rule defined in the job
            for rule in job.rules:

                # Options passed to data retrieval layer
                options = {"return_polars": True}

                # Fetch required dataset for rule evaluation
                df = get_data(
                    symbol=rule.symbol,
                    timeframe=rule.timeframe,
                    after_ms=int((time.time() - 86400 * 5) * 1000),
                    limit=100000,
                    order="asc",
                    indicators=rule.indicators,
                    options=options,
                )

                # Evaluate rule conditions against retrieved dataset
                is_triggered = RuleEvaluator.evaluate(df, rule)

                if is_triggered:
                    # Log rule trigger event
                    print(f"  -> Rule '{rule.name}' TRIGGERED on {rule.symbol}!")

                    # Extract most recent row for payload context
                    latest_data = df.tail(1).to_dicts()[0]

                    # Build action payload
                    payload = {
                        "job": job.name,
                        "rule": rule.name,
                        "symbol": rule.symbol,
                        "time": current_time.isoformat(),
                        "data": latest_data,
                    }

                    # Dispatch all configured actions
                    for action in job.actions:
                        ActionFactory.dispatch(
                            action.type,
                            action.params,
                            payload,
                        )
                else:
                    # Log non-triggered rule outcome
                    print(f"  -> Rule '{rule.name}' conditions not met.")