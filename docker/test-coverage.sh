#!/bin/sh

cat << EOF
==========================================
== Begin DAMS Storage API test coverage ==
==========================================
EOF

coverage report -m

cat << EOF
========================================
== End DAMS Storage API test coverage ==
========================================
EOF
