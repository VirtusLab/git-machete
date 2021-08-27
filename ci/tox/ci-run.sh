#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ci/docker-build-and-push.sh tox

docker-compose --ansi never -f /home/circleci/project/ci/tox/docker-compose.yml run tox
