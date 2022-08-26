#!/usr/bin/env bash

set -e -o pipefail -u

source "$(git rev-parse --show-toplevel)"/ci/local-run-commons.sh rpm

export_directory_hash rpm
cd "$(git rev-parse --show-toplevel)"/ci/rpm/

set -x
docker-compose build rpm
docker-compose run -e GID="$(id -g)" -e UID="$(id -u)" rpm
