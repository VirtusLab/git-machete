#!/usr/bin/env bash

set -e -o pipefail -u -x

DIRECTORY_HASH=$(git rev-parse HEAD:ci/tox)
export DIRECTORY_HASH
cd ci/tox/

docker-compose up --exit-code-from=tox tox
