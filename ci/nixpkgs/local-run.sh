#!/usr/bin/env bash

set -e -o pipefail -u -x

source "$(git rev-parse --show-toplevel)"/ci/local-run-commons.sh

export_directory_hash nixpkgs
cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs/

git_revision=$(git rev-parse "@{upstream}")
docker-compose --progress=plain build nixpkgs
docker-compose run -e GIT_REVISION="$git_revision" nixpkgs
