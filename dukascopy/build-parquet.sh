#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 builder/run.py --parquet "$@"