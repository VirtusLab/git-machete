#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs-pr/

[[ ${VERSION-} ]] || { echo "Var VERSION is missing from environment"; exit 1; }

set -x

hash=$(git rev-parse HEAD:ci/nixpkgs-pr)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
else
  export DIRECTORY_HASH="$hash"-dirty
fi

docker-compose build nixpkgs-pr
docker-compose run -e DO_PUSH=false -e PYPI_HOST=test.pypi.org nixpkgs-pr
