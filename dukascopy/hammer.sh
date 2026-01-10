#!/bin/bash

# This is a test hammering script to hammer the API endpoint
# In order to see what happens when DUCKDB registration of a changed underlying view is happening
# Are we safe?

URL="http://localhost:8000/ohlcv/1.0/select/BTC-USD,1d/after/2025-01-01+00:00:00/output/JSON?page=1&order=desc&limit=1000"
CONCURRENCY=128

echo "Starting stress test with $CONCURRENCY concurrent processes..."
echo "Press [CTRL+C] to stop."

do_request() {
  while true; do
    response=$(curl -s -w "\n%{http_code}" "$URL")
    
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)

    if [[ "$status" -ne 200 ]] || [[ "$body" == *"failure"* ]] || [[ "$body" == *"exception"* ]]; then
      echo -e "\n[ERROR] Status: $status"
      echo "Response Body: $body"
      echo "--------------------------------------------------"
    fi
  done
}

export -f do_request
export URL

# Use xargs to run the function in 10 parallel background processes
seq $CONCURRENCY | xargs -I{} -P $CONCURRENCY bash -c "do_request"