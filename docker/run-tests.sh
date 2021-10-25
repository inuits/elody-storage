#!/bin/sh

export PATH=${PATH}:/app/.local/bin
export REQUIRE_TOKEN=0
export MINIO_ENDPOINT=http://localhost:5000
export MINIO_BUCKET=test
export MINIO_ACCESS_KEY=test
export MINIO_SECRET_KEY=test

cat << EOF
=========================================
== Begin DAMS Storage API test results ==
=========================================
EOF

moto_server s3 > /dev/null 2>&1 &
coverage run -m pytest -s

cat << EOF
=======================================
== End DAMS Storage API test results ==
=======================================
EOF
