#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ci/docker-build-and-push.sh rpm

docker-compose run rpm
