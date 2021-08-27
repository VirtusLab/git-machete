#!/usr/bin/env bash

set -e -o pipefail -u -x

bash ../docker-build-and-push.sh rpm

docker-compose run rpm
