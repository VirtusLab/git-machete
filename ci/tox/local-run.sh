#!/usr/bin/env bash

set -e -o pipefail -u

source ../local-run-commons.sh tox

export_directory_hash tox
cd "$(git rev-parse --show-toplevel)"/ci/tox/
check_var GIT_VERSION
check_var PYTHON_VERSION

set -x
export TARGET=local
export MOUNT_POINT=/home/ci-user
docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" tox
docker-compose run tox