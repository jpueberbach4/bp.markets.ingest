#!/bin/bash

# Preferably run this script on UTC saturday
NUMDAYS=7

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
            shift
            ;;
    esac
done

# Get exclusive lock
mkdir -p "$(pwd)/data/locks"
exec 200>"$(pwd)/data/locks/run.lock"
flock -x 200  

echo "Stopping services...."
./service.sh stop > /dev/null 2>&1
echo "Done."


# Clean Cached JSON and Transform CSV
for ((i=1; i<=NUMDAYS; i++)); do
    DATE_PART=$(date -d "-$i days" +%Y/%m/*_%Y%m%d)
    
    # If symbols are specified, target them. Otherwise, use wildcard.
    if [ ${#SYMBOLS[@]} -gt 0 ]; then
        for symbol in "${SYMBOLS[@]}"; do
            rm -f cache/${DATE_PART%/*}/${symbol}_$(date -d "-$i days" +%Y%m%d).json 2>/dev/null
            rm -f data/transform/1m/${DATE_PART%/*}/${symbol}_$(date -d "-$i days" +%Y%m%d).* 2>/dev/null
        done
    else
        # Global wipe for the day
        rm -f cache/${DATE_PART}.json 2>/dev/null
        rm -f data/transform/1m/${DATE_PART}.* 2>/dev/null
    fi
done

# Clean Higher Layers (Aggregate / Resample / Temp)
TARGET_DIRS=("./data/aggregate" "./data/resample" "./data/temp")

if [ ${#SYMBOLS[@]} -gt 0 ]; then
    echo "Targeted mode: Cleaning higher layers for: ${SYMBOLS[*]}"
    for dir in "${TARGET_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            for symbol in "${SYMBOLS[@]}"; do
                find "$dir" -name "${symbol}*" -exec rm -rf {} +
            done
        fi
    done
else
    echo "General mode: Cleaning all higher layers..."
    for dir in "${TARGET_DIRS[@]}"; do
        rm -rf "$dir"
    done
fi

# Rebuild
echo "Rebuilding..."
export PYTHONPATH=$PYTHONPATH:$(pwd)
# We keep START_DATE=2005-01-01 as per your original script to allow the 
# engine to verify the full chain, but it will only work on what's missing.
START_DATE=2005-01-01 NOLOCK=1 ./run.sh

echo "Done."

# Release lock
exec 200>&-

echo "Restarting services...."
./service.sh restart > /dev/null 2>&1
echo "Done."