#!/bin/sh

set -e

if [ "$APP_ENV" = "dev" ]; then
  echo "Starting development server..."
  exec flask run --host=0.0.0.0
else
  echo "Starting gunicorn server..."
  exec gunicorn -b 0.0.0.0:8001 app:app
fi

