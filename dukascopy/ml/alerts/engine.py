import time
from datetime import datetime
from typing import List, Dict, Any
from ml.alerts.models import AlertJob, ActionConfig, Rule, Condition
from ml.alerts.evaluator import RuleEvaluator
from ml.alerts.actions import ActionFactory
from util.api import get_data
import re

class AlertEngine:
    def __init__(self, config: Any):
        self.config = config
        self.jobs = self._parse_config(config)

    def _parse_config(self, raw: Any) -> List[AlertJob]:
        jobs = []
        for job_name, data in raw.items():
            actions = []
            # Use .items() to cleanly unpack the dictionary keys and values
            for name, params in data.get('actions', {}).items():
                print(f"Loading action module: {name}")
                actions.append(ActionConfig(name=name, type=params.get('type'), params=params))
            
            rules = []
            for r in data.get('rules', []):
                r_name = list(r.keys())[0]
                r_data = r[r_name]
                
                conditions = []
                for c in r_data.get('conditions', []):
                    c_name = list(c.keys())[0]
                    c_data = c[c_name]
                    conditions.append(Condition(
                        name=c_name,
                        column=c_data['column'],
                        operator=c_data['operator'],
                        value=c_data['value']
                    ))
                    
                rules.append(Rule(
                    name=r_name,
                    symbol=r_data['symbol'],
                    timeframe=r_data['timeframe'],
                    indicators=r_data['indicators'],
                    conditions=conditions
                ))
                
            jobs.append(AlertJob(
                name=job_name,
                weekdays=data.get('weekdays', []),
                run_at=data.get('run-at'),
                from_date=data.get('from_date'),
                to_date=data.get('to_date'),
                actions=actions,
                rules=rules
            ))
        return jobs

    def process_jobs(self):
        current_time = datetime.now()
        current_weekday = current_time.weekday()
        current_hms = current_time.strftime('%H:%M:00')

        for job in self.jobs:
            # weekday check
            if current_weekday not in job.weekdays:
                continue

            # from_date, to_date check
            try:
                fmt = '%Y-%m-%d'
                job_start = job.from_date if isinstance(job.from_date, datetime) else datetime.strptime(str(job.from_date), fmt)
                job_end = job.to_date if isinstance(job.to_date, datetime) else datetime.strptime(str(job.to_date), fmt)
                
                if not (job_start <= current_time <= job_end):
                    continue
            except Exception as e:
                print(f"[Schedule Error] Date parsing failed for job {job.name}: {e}")
                continue

            # run-at check (with wildcard support)
            if job.run_at and str(job.run_at).strip():
                # replace a * with .. (2 characters)
                pattern_str = str(job.run_at).replace('*', '..')
                pattern = f"^{pattern_str}$"
                
                if not re.match(pattern, current_hms):
                    # no match, next job
                    continue

            print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Executing Job: {job.name}")
            
            for rule in job.rules:
                options = {"return_polars": True}
                
                df = get_data(
                    symbol=rule.symbol,
                    timeframe=rule.timeframe,
                    after_ms=int((time.time() - 86400 * 5) * 1000), 
                    limit=100000,
                    order="asc",
                    indicators=rule.indicators,
                    options=options
                )
                
                is_triggered = RuleEvaluator.evaluate(df, rule)
                
                if is_triggered:
                    print(f"  -> Rule '{rule.name}' TRIGGERED on {rule.symbol}!")
                    
                    latest_data = df.tail(1).to_dicts()[0]
                    
                    payload = {
                        "job": job.name,
                        "rule": rule.name,
                        "symbol": rule.symbol,
                        "time": current_time.isoformat(),
                        "data": latest_data
                    }
                    
                    for action in job.actions:
                        ActionFactory.dispatch(action.type, action.params, payload)
                else:
                    print(f"  -> Rule '{rule.name}' conditions not met.")