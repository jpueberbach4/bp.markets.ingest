#!/bin/bash

# Parse Arguments
SYMBOL_PREFIX=""
if [[ "$1" == "--symbol" ]] && [[ -n "$2" ]]; then
    SYMBOL_PREFIX="$2"
    echo "Targeted mode: Recursively cleaning files starting with $SYMBOL_PREFIX..."
else
    echo "General mode: Cleaning all folders..."
fi

# Get exclusive lock
mkdir -p "$(pwd)/data/locks"
exec 200>"$(pwd)/data/locks/run.lock"
flock -x 200  

# Targeted or Global Deletion
TARGET_DIRS=("./data/transform" "./data/aggregate" "./data/resample" "./data/temp")

for dir in "${TARGET_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        if [ -n "$SYMBOL_PREFIX" ]; then
            # Find and remove files/folders starting with prefix in any subfolder
            # -name matches the prefix, -delete handles the removal
            echo "Searching $dir for files starting with $SYMBOL_PREFIX..."
            find "$dir" -name "${SYMBOL_PREFIX}*" -exec rm -rf {} +
        else
            # Default behavior: remove the whole directory content
            echo "Deleting all contents of $dir..."
            rm -rf "$dir"
        fi
    fi
done

# Rebuild
echo "Rebuilding..."
export PYTHONPATH=$PYTHONPATH:$(pwd)
START_DATE=2005-01-01 NOLOCK=1 ./run.sh

echo "Done."

# Release lock
exec 200>&-

Echo "Restarting services...."
./service.sh restart
echo "Done."