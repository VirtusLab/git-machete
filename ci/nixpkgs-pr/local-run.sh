#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/nixpkgs-pr/

[[ ${VERSION-} ]] || { echo "Var VERSION is missing from environment"; exit 1; }

set -x

if git diff-index --quiet HEAD .; then
  DIRECTORY_HASH=$(git rev-parse HEAD:ci/nixpkgs-pr)
  export DIRECTORY_HASH
  docker-compose pull nixpkgs-pr || docker-compose build nixpkgs-pr
else
  export DIRECTORY_HASH=unspecified
  docker-compose build nixpkgs-pr
fi

docker-compose up --exit-code-from=nixpkgs-pr nixpkgs-pr
