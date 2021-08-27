#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ci/docker-build-and-push.sh tox

cd ci/tox/
docker-compose --ansi never run tox
