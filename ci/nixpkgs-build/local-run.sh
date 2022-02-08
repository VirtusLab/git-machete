#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs-build/

source ../local-run-commons.sh nixpkgs-build
export_directory_hash nixpkgs-build

git_revision=$(git rev-parse "@{upstream}")

docker-compose build nixpkgs-build
docker-compose run -e GIT_REVISION=$git_revision nixpkgs-build
