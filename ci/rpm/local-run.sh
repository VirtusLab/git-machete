#!/usr/bin/env bash

set -e -o pipefail -u

function build_image() {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
}

cd "$(git rev-parse --show-toplevel)"/ci/rpm/

set -x

hash=$(git rev-parse HEAD:ci/rpm)
if git diff-index --quiet HEAD .; then
  export DIRECTORY_HASH="$hash"
  docker-compose pull rpm || build_image
else
  export DIRECTORY_HASH="$hash"-dirty
  build_image
fi

docker-compose up --exit-code-from=rpm rpm
