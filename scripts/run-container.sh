#!/bin/bash
DOCKER=docker
if [ -x "$(command -v podman)" ]; then
  DOCKER=podman
fi

${DOCKER} run -it --rm -p 8000:8000 --env APP_ENV=production inuits-dams-collection-api:latest $@
