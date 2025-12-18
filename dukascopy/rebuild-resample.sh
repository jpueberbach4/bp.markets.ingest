#!/bin/bash

# Get exclusive lock
exec 200>`pwd`/data/locks/run.lock
flock -x 200  
echo Deleting data/resample*...
rm -rf ./data/resample
echo Rebuilding...
START_DATE=2005-01-01 NOLOCK=1 ./run.sh
echo Done.
# Release lock
exec 200>&-