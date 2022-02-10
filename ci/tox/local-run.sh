#!/usr/bin/env bash

set -e -o pipefail -u

source ../local-run-commons.sh tox

export_directory_hash tox
cd "$(git rev-parse --show-toplevel)"/ci/tox/
check_var GIT_VERSION
check_var PYTHON_VERSION

set -x
export TARGET=LOCAL
export MOUNT_POINT=home/ci-user
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" tox
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose run tox