#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ci/docker-build-and-push.sh tox

docker-compose run tox
