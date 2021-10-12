#!/bin/sh

set -e

if [ ! -z "$@" ]; then
  echo "Running command: $@"
  exec $@
  exit $?
fi

if [ "$APP_ENV" = "dev" ]; then
  echo "Starting development server..."
  export FLASK_ENV=development
  cd ~/api
  exec ~/.local/bin/flask run --host=0.0.0.0 --port=8000
else
  echo "Starting gunicorn server..."
  cd ~/api
  exec ~/.local/bin/gunicorn -b 0.0.0.0:8000 "app:app"
fi

