#!/bin/sh
set -e

if [ "$ENV" = "development" ]; then
    echo "Running development server..."
    exec python run_dev.py
else
    echo "Running production server..."
    exec gunicorn -w "$WORKERS" -b $FLASK_RUN_HOST:$FLASK_PORT wsgi:app
fi
