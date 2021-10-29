#!/bin/bash
DOCKER=docker
if [ -x "$(command -v podman)" ]; then
  DOCKER=podman
fi

${DOCKER} run -it --rm -p 8001:8001 --env APP_ENV=production inuits-dams-storage-api:latest $@
