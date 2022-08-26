#!/usr/bin/env bash

set -e -o pipefail -u -x

source "$(git rev-parse --show-toplevel)"/ci/ci-run-commons.sh

git_revision=$(git rev-parse HEAD)
docker_compose_pull_or_build_and_push nixpkgs-build
docker-compose --ansi=never run -e GIT_REVISION="$git_revision" nixpkgs-build
