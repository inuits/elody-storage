#!/bin/bash

__DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DOCKER=docker
if [ -x "$(command -v podman)" ]; then
  DOCKER=podman
fi

${DOCKER} run -it --rm -v ${__DIR}/api:/app/api -p 8001:8001 inuits-dams-storage-api:dev $@
