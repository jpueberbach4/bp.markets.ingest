#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m unittest discover tests