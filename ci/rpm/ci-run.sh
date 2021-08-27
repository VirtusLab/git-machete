#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ci/docker-build-and-push.sh rpm

cd ci/rpm/
docker-compose --ansi never run rpm
