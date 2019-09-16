#!/usr/bin/env bash

set -e -o pipefail -u

function build_image() {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
}

cd "$(git rev-parse --show-toplevel)"/ci/rpm/

set -x

if git diff-index --quiet HEAD .; then
  DIRECTORY_HASH=$(git rev-parse HEAD:ci/rpm)
  export DIRECTORY_HASH
  docker-compose pull rpm || build_image
else
  export DIRECTORY_HASH=unspecified
  build_image
fi

docker-compose up --exit-code-from=rpm rpm
