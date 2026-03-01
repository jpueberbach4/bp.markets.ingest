#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)

python3 ml/diagnostics/run.py "$@"
