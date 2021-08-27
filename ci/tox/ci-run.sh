#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ./docker-build-and-push.sh tox

docker-compose run tox
