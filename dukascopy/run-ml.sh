#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)

unset LD_LIBRARY_PATH

echo "🛰️ [Space]: Passing coordinates: $@"

python3 ml/run.py "$@"

# Capture the exit code of the singularity
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ [Space]: Mission successful. Flight path cleared."
else
    echo "🚨 [Space]: Singularity collapse. Exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi