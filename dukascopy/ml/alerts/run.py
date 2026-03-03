import time
import os
from ml.alerts.engine import AlertEngine
from util.config import load_app_config

def main():

    paths = [
        'config.user.yaml',
        'config.yaml'
    ]

    app_config = load_app_config(
        [p for p in paths if os.path.isfile(p)][0]
    )

    alerts_config = app_config.ml.get('alerts')

    engine = AlertEngine(alerts_config)
    try:
        engine.process_jobs()
    except Exception as e:
        print(f"[System Error] Engine loop failed: {e}")

if __name__ == "__main__":
    main()