#!/usr/bin/env bash

set -e -o pipefail -u

cd "$(git rev-parse --show-toplevel)"/ci/rpm/

set -x

bash ../export-hash.sh rpm

docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
docker-compose run rpm
