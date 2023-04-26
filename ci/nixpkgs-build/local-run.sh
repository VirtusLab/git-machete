#!/usr/bin/env bash

set -e -o pipefail -u -x

source "$(git rev-parse --show-toplevel)"/ci/local-run-commons.sh nixpkgs-build

export_directory_hash nixpkgs-build
cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs-build/

git_revision=$(git rev-parse "@{upstream}")
docker-compose --progress=plain build nixpkgs-build
docker-compose run -e GIT_REVISION="$git_revision" nixpkgs-build
