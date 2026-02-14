#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 generators/sidetracking/run.py "$@"