#!/bin/bash

# Preferably run this script on UTC saturday
NUMDAYS=7

# Get exclusive lock
exec 200>`pwd`/data/locks/run.lock
flock -x 200  

echo Deleting cached JSON data for last $NUMDAYS
sleep 0.5
for ((i=1; i<=NUMDAYS; i++)); do
    GLOB_PATTERN=$(date -d "-$i days" +cache/%Y/%m/*_%Y%m%d.json)
    for file in $GLOB_PATTERN; do
        if [ -f "$file" ]; then
            echo "Deleting $file"
            rm "$file"
        fi
    done
done

echo Deleting transform CSV data for last $NUMDAYS
sleep 0.5
for ((i=1; i<=NUMDAYS; i++)); do
    GLOB_PATTERN=$(date -d "-$i days" +data/transform/1m/%Y/%m/*_%Y%m%d.csv)
    for file in $GLOB_PATTERN; do
        if [ -f "$file" ]; then
            echo "Deleting $file"
            rm "$file"
        fi
    done
done

echo Deleting data/*...
rm -rf ./data/resample ./data/aggregate ./data/temp
echo Rebuilding...
export PYTHONPATH=$PYTHONPATH:$(pwd)
START_DATE=2005-01-01 NOLOCK=1 ./run.sh
echo Done.
# Release lock
exec 200>&-