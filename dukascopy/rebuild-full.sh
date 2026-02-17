#!/bin/bash

# Parse Arguments
SYMBOLS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --symbol)
            if [[ -n "$2" ]]; then
                SYMBOLS+=("$2")
                shift 2
            else
                echo "Error: --symbol requires an argument."
                exit 1
            fi
            ;;
        *)
            # Ignore unknown arguments or handle them here
            shift
            ;;
    esac
done

# Check mode
if [ ${#SYMBOLS[@]} -gt 0 ]; then
    echo "Targeted mode: Recursively cleaning files for: ${SYMBOLS[*]}"
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
        if [ ${#SYMBOLS[@]} -gt 0 ]; then
            for symbol in "${SYMBOLS[@]}"; do
                echo "Searching $dir for files starting with $symbol..."
                # Using -name with find to catch files in subdirectories
                find "$dir" -name "${symbol}*" -exec rm -rf {} +
            done
        else
            # Default behavior: remove the whole directory content
            echo "Deleting all contents of $dir..."
            # Using find -mindepth 1 to delete contents but keep the root folder
            find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
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

echo "Restarting services...."
./service.sh restart
echo "Done."