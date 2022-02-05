#!/usr/bin/env bash

set -e -o pipefail -u -x

source ci/docker-pull-or-build-and-push.sh nixpkgs-build

git_revision=$(git rev-parse HEAD)
docker-compose --ansi never run -e GIT_REVISION=$git_revision nixpkgs-build
