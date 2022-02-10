#!/usr/bin/env bash

set -e -o pipefail -u

source ../local-run-commons.sh rpm
export_directory_hash rpm
cd "$(git rev-parse --show-toplevel)"/ci/rpm/

set -x
export TARGET=local
export MOUNT_POINT=/home/ci-user
docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
docker-compose run rpm
