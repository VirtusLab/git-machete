#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/rpm/

set -x

hash=$(git rev-parse HEAD:ci/rpm)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
else
  export DIRECTORY_HASH="$hash"-dirty
fi

docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
docker-compose run rpm
