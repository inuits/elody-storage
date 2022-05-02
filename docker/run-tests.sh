#!/bin/sh

export PATH=${PATH}:/app/.local/bin
export REQUIRE_TOKEN=0
export MINIO_ENDPOINT=http://localhost:3000
export MINIO_BUCKET=test
export MINIO_ACCESS_KEY=test
export MINIO_SECRET_KEY=test
export FLASK_ENV=development

cat << EOF
=========================================
== Begin DAMS Storage API test results ==
=========================================
EOF

moto_server -p3000 s3 > /dev/null 2>&1 &
coverage run -m pytest -s

cat << EOF
=======================================
== End DAMS Storage API test results ==
=======================================
EOF
