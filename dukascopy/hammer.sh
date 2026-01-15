#!/bin/bash

# Configuration
URL="http://localhost:8000/ohlcv/1.1/select/EUR-USD,1m[sma(9):sma(18):sma(32):sma(48):sma(64):sma(100):bbands(20,2.0):sma(200)]/after/2026-01-10%2000:00:59/until/2026-01-12%2000:00:59/output/JSONP?order=asc&limit=1440&callback=__callbackData"
CONCURRENT_REQUESTS=64
TOTAL_REQUESTS=500

echo "Starting hammer test on $URL"
echo "Sending $TOTAL_REQUESTS total requests ($CONCURRENT_REQUESTS at a time)..."

# Function to perform a single request
send_request() {
    # -s: silent, -o /dev/null: discard output, -w: format output
    curl -g -sS -o /dev/null -w "Request #$i | Status: %{http_code} | Total Time: %{time_total}s\n" "$URL" &
}

# Main loop
for ((i=1; i<=TOTAL_REQUESTS; i++)); do
    echo Hammering.. $i
    send_request &
    
    # Check if we've hit the concurrency limit
    if [[ $(jobs -r -p | wc -l) -ge $CONCURRENT_REQUESTS ]]; then
        wait -n # Wait for at least one background job to finish
    fi
done

wait # Wait for all remaining background jobs to finish
echo "Hammering complete."