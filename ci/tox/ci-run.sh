#!/usr/bin/env bash

set -e -o pipefail -u -x

source ci/docker-build-and-push.sh tox

docker-compose --ansi never run tox
