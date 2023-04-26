#!/usr/bin/env bash

set -e -o pipefail -u

source "$(git rev-parse --show-toplevel)"/ci/local-run-commons.sh tox

export_directory_hash tox
cd "$(git rev-parse --show-toplevel)"/ci/tox/
check_var GIT_VERSION
check_var PYTHON_VERSION

set -x
docker-compose --progress=plain build tox
docker-compose run -e GID="$(id -g)" -e UID="$(id -u)" tox
