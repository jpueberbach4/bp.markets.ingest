#!/bin/bash

# Get exclusive lock
exec 200>`pwd`/data/locks/run.lock
flock -x 200  
echo Deleting data/*...
rm -rf ./data/transform ./data/aggregate ./data/resample ./data/temp
echo Rebuilding...
START_DATE=2025-01-01 NOLOCK=1 ./run.sh
echo Done.
# Release lock
exec 200>&-