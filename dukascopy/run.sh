#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)

python3 etl/run.py
