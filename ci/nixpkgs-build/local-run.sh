#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs-build/

set -x

hash=$(git rev-parse HEAD:ci/nixpkgs-build)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
else
  export DIRECTORY_HASH="$hash"-dirty
fi
git_revision=$(git rev-parse "@{upstream}")

docker-compose build nixpkgs-build
docker-compose run -e GIT_REVISION=$git_revision nixpkgs-build
