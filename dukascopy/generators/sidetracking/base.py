#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        dukascopy_panama.py
Author:      JP Ueberbach
Created:     2025-02-14

Purpose:
    Defines the core adjustment framework used to generate deterministic,
    auditable back-adjustment configurations for market data.

    This module provides:
        - A strict strategy interface for adjustment logic
        - A normalized time-window action model
        - A configuration generator that serializes adjustments into YAML

    While commonly used with Panama-style rollover adjustments (e.g.
    Dukascopy monthly roll data), this module itself is strategy-agnostic
    and supports any forward-only adjustment model.

Design Notes:
    - Uses the Strategy pattern to decouple data acquisition from math
    - Enforces a clean separation between I/O, logic, and serialization
    - Produces explicit time windows instead of mutating price data
    - Output is deterministic, human-readable, and diff-friendly
    - Designed to scale across thousands of symbols consistently

What This Module Does:
    - Defines the IAdjustmentStrategy contract
    - Defines the TimeWindowAction data model
    - Orchestrates strategy execution
    - Serializes adjustment windows into YAML

What This Module Does NOT Do:
    - Does NOT fetch candles or ticks directly
    - Does NOT apply adjustments to price series
    - Does NOT perform scheduling or parallel execution
    - Does NOT infer or guess corporate actions
    - Does NOT hide logic behind opaque binaries or vendor APIs

Complexity:
    - Strategy fetch: implementation-defined
    - Action generation: typically O(N) or O(N log N)
    - YAML serialization: O(N)
    - Overall complexity dominated by chosen strategy

Requirements:
    - Python 3.8+
    - PyYAML
    - Standard library only (abc, dataclasses, datetime, typing)

License:
    MIT License
===============================================================================
"""
import abc
import yaml
from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class TimeWindowAction:
    # Plain data container → no logic → O(1)
    id: str
    action: str
    columns: List[str]
    value: float
    from_date: datetime
    to_date: datetime


class IAdjustmentStrategy(abc.ABC):

    @abc.abstractmethod
    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetches and normalizes external adjustment data.

        This method is responsible for connecting to an external data source
        (API, file, database, etc.) and returning a normalized list of events
        that can later be converted into time-window adjustments.

        Args:
            symbol: Internal symbol identifier used by the strategy.

        Returns:
            A list of dictionaries representing normalized adjustment events.
        """
        # Interface method only → no implementation → O(1)
        pass

    @abc.abstractmethod
    def generate_config(
        self,
        symbol: str,
        raw_data: List[Dict[str, Any]]
    ) -> List[TimeWindowAction]:
        """Generates adjustment windows from raw event data.

        This method applies strategy-specific logic (e.g. Panama, splits,
        dividends) to transform raw events into concrete TimeWindowAction
        objects.

        Args:
            symbol: Internal symbol identifier.
            raw_data: Normalized data returned by `fetch_data`.

        Returns:
            A list of TimeWindowAction objects defining adjustment windows.
        """
        # Interface method only → no implementation → O(1)
        pass


class ConfigGenerator:
    def __init__(self, strategy: IAdjustmentStrategy):
        """Initializes the configuration generator.

        Args:
            strategy: An implementation of IAdjustmentStrategy that
                defines how data is fetched and transformed.
        """
        # Simple assignment → O(1)
        self.strategy = strategy

    def build_yaml(self, symbol: str, source_name: str) -> str:
        """Builds a YAML configuration using the provided strategy.

        This method orchestrates the full workflow:
            1. Fetch raw adjustment data
            2. Generate time-window actions
            3. Serialize the result into a YAML configuration

        Args:
            symbol: Target symbol name used in the final YAML.
            source_name: Symbol name passed to the data source.

        Returns:
            A YAML-formatted string containing adjustment configuration,
            or a comment string if no data is available.
        """
        # Fetch remote or external data via strategy → complexity depends on strategy
        data = self.strategy.fetch_data(source_name)
        
        # Guard clause: no data means no configuration → O(1)
        if not data:
            raise Exception(f"# No data found or error occurred for {source_name}")

        # Convert raw data into time-window actions → typically O(N) or O(N log N)
        window_actions = self.strategy.generate_config(source_name, data)
        
        # Prepare dictionary for YAML serialization → O(1)
        post_processors = {}

        # Iterate over all generated actions → O(N)
        for act in window_actions:
            post_processors[act.id] = {
                "action": act.action,
                "columns": act.columns,
                "value": act.value,
                # Datetime formatting → O(1)
                "from_date": act.from_date.strftime("%Y-%m-%d %H:%M:%S"),
                "to_date": act.to_date.strftime("%Y-%m-%d %H:%M:%S")
            }

        # Final nested configuration structure → O(1)
        final_config = {
            f"{symbol}": {
                "source": source_name,
                "post": post_processors
            }
        }

        # YAML serialization walks entire structure → O(N)
        return yaml.dump(final_config, sort_keys=False)
