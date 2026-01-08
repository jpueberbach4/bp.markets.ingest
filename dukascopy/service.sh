#!/bin/bash

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
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        echo "Stopping: $SERVICE_NAME (PID: $PID)..."
        kill $PID && rm $PIDFILE
    else
        echo "Not Running: No PID file found for $SERVICE_NAME."
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  pgrep -fl "$SERVICE_NAME" || echo "Service is stopped." ;;
    *)       echo "Usage: $0 {start|stop|restart|status}" ;;
esac