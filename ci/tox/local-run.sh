#!/usr/bin/env bash

set -e -o pipefail -u

function check_var() {
  [[ ${!1-} ]] && return 0 || true
  [[ -f .env ]] || { echo "Var $1 missing from environment and no .env file found; see .env.sample file"; return 1; }
  grep -q "^$1=" .env || { echo "Var $1 missing both from environment and .env file"; return 1; }
}

function build_image() {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" tox
}

cd "$(git rev-parse --show-toplevel)"/ci/tox/
check_var GIT_VERSION
check_var PYTHON_VERSION

set -x

hash=$(git rev-parse HEAD:ci/tox)
if git diff-index --quiet HEAD .; then
  DIRECTORY_HASH=$(git rev-parse HEAD:ci/tox)
  export DIRECTORY_HASH="$hash"
  docker-compose pull tox || build_image
else
  export DIRECTORY_HASH="$hash"-dirty
  build_image
fi

docker-compose up --exit-code-from=tox tox
