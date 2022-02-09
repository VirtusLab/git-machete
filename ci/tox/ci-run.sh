#!/usr/bin/env bash

set -e -o pipefail -u -x

source ci/docker-pull-or-build-and-push.sh tox

ls -al
docker-compose --ansi never run tox
