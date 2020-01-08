#!/usr/bin/env bash

set -e -o pipefail -u -x

DOCKER_TAG=$(git rev-parse HEAD:ci/rpm/)
export DOCKER_TAG
cd ci/rpm/

# If the image corresponding to the current state of ci/rpm/ is missing, build it and push to Docker Hub.
docker-compose pull rpm || {
  docker-compose build --build-arg user_id="$(id -u)" --build-arg group_id="$(id -g)" rpm
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  docker-compose push rpm
}

docker-compose up --exit-code-from=rpm rpm
