#!/bin/sh

set -e
GUNICORN_SSL_CA=""

if [ ! -z "$@" ]; then
  echo "Running command: $@"
  exec $@
  exit $?
fi

if [ ! -z "$TRUSTED_CA_BUNDLE" ]; then
  cp /etc/ssl/certs/ca-certificates.crt /tmp/ca-certificates.crt
  echo "${TRUSTED_CA_BUNDLE}" >> /tmp/ca-certificates.crt
  export CURL_CA_BUNDLE="/tmp/ca-certificates.crt"
  GUNICORN_SSL_CA=" --ca-certs /tmp/ca-certificates.crt"
fi

if [ "$APP_ENV" = "dev" ]; then
  echo "Starting development server..."
  export FLASK_DEBUG='1'
  cd ~/api
  exec ~/.local/bin/flask run --host=0.0.0.0
else
  echo "Starting gunicorn server..."
  cd ~/api
  exec ~/.local/bin/gunicorn ${GUNICORN_SSL_CA} -b 0.0.0.0 --timeout 0 "app:app" --access-logfile - --access-logformat '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(M)sms %(b)s "%(f)s" "%(a)s"'
fi

