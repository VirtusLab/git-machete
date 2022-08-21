#!/usr/bin/env bash

set -e -o pipefail -u -x

source "$(git rev-parse --show-toplevel)"/ci/ci-run-commons.sh

docker_compose_pull_or_build_and_push rpm
docker-compose --ansi=never run rpm
