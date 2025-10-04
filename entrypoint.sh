#!/bin/sh
set -e

if [ "$ENV" = "development" ]; then
    echo "Running development server..."
    exec python run_dev.py
else
    echo "Running production server..."
    exec gunicorn -w "$WORKERS" -b 0.0.0.0:$FLASK_PORT app.wsgi:app
fi
