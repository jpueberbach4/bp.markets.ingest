#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)

python3 ml/alerts/run.py "$@"
