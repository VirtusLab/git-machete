#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs-pr/

[[ ${VERSION-} ]] || { echo "Var VERSION is missing from environment"; exit 1; }

set -x

hash=$(git rev-parse HEAD:ci/nixpkgs-pr)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
  docker-compose pull nixpkgs-pr || docker-compose build nixpkgs-pr
else
  export DIRECTORY_HASH="$hash"-dirty
  docker-compose build nixpkgs-pr
fi

docker-compose up --exit-code-from=nixpkgs-pr nixpkgs-pr
