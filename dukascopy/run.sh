#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)

SLEEP_TIME=$(python3 -c "import random; print(random.uniform(5, 31))")

echo "Staggering start: sleeping for ${SLEEP_TIME}s to avoid thundering herd..."
sleep $SLEEP_TIME

python3 etl/run.py
