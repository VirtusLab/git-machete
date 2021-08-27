#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ci/docker-build-and-push.sh rpm

docker-compose --ansi never -f /home/circleci/project/ci/rpm/docker-compose.yml run rpm
