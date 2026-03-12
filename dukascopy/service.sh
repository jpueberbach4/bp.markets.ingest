#!/bin/bash

unset LD_LIBRARY_PATH

SERVICE_NAME="api/run.py"
PIDFILE="./data/http.pid"

start() {
    if [ -f $PIDFILE ] && kill -0 $(cat $PIDFILE) 2>/dev/null; then
        echo "Running: $SERVICE_NAME is already active (PID: $(cat $PIDFILE))"
    else
        echo "Starting: $SERVICE_NAME..."
        export PYTHONPATH=$PYTHONPATH:$(pwd)
        python3 $SERVICE_NAME &
        echo $! > $PIDFILE
    fi
}

stop() {
    echo "Stopping all Python processes related to $SERVICE_NAME..."

    pkill -f "$SERVICE_NAME"

    pkill -f "multiprocessing.resource_tracker"
    pkill -f "multiprocessing.spawn"

    rm -f $PIDFILE
    
    sleep 2
    echo "Cleanup complete."
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 2; start ;;
    status)  pgrep -fl "$SERVICE_NAME" || echo "Service is stopped." ;;
    *)       echo "Usage: $0 {start|stop|restart|status}" ;;
esac